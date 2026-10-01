from django.db import transaction
from django.db.models import F
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.chatgpt.models import ChatgptAccount, ChatgptCar
from app.chatgpt.serializers import ShowChatgptTokenSerializer, AddChatgptTokenSerializer, ChatGPTLoginSerializer, \
    UpdateChatgptInfoSerializer, DeleteChatgptAccountSerializer, CheckChatgptTokenExpirySerializer, \
    RefreshChatgptTokenSerializer, ResetChatgptLoginCountSerializer
from app.page import DefaultPageNumberPagination
from app.settings import CHATGPT_GATEWAY_URL
from app.utils import get_request_subject, save_visit_log, req_gateway
from app.accounts.models import User
from app.accounts.session_authority import gateway_authorization, capability_aliases, account_model_policy
from app.accounts.views.announcements import active_login_block_for
from rest_framework.exceptions import PermissionDenied, ValidationError

def build_token_expiry_result(account, error="", auth_state=None):
    return {
        "id": account.id,
        "chatgpt_username": account.chatgpt_username,
        "access_token_exp": None,
        "access_token_iat": None,
        "remaining_seconds": None,
        "expired": None,
        "expiry_status": "unknown",
        "access_token_valid": account.access_token_valid,
        "session_token_valid": account.session_token_valid,
        "auth_state": auth_state or account.auth_state,
        "last_check_at": account.last_check_at,
        "last_error": account.last_error or error,
        "has_refresh_token": False,
    }


class ChatGPTAccountEnum(APIView):
    permission_classes = (IsAuthenticated, IsAdminUser)

    def get(self, request):
        result = ChatgptAccount.objects.filter(auth_status=True).order_by("-id").values(
            "id", "chatgpt_username", "plan_type").all()
        return Response({"data": result})


class ChatGPTAccountView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, IsAdminUser)

    @staticmethod
    def _validate_proxy_node(proxy_node_id):
        config = req_gateway("get", "/api/mirror-proxy-config")
        require_proxy = bool(config.get("claude_require_proxy"))
        if proxy_node_id is None:
            if require_proxy:
                raise ValidationError({"proxy_node_id": "当前服务要求选择启用的代理节点"})
            return config
        node_ids = {
            int(node.get("id"))
            for node in (config.get("nodes") or [])
            if isinstance(node, dict) and node.get("enabled") and str(node.get("id") or "").isdigit()
        }
        if proxy_node_id not in node_ids:
            raise ValidationError({"proxy_node_id": "代理节点不存在或未启用"})
        return config

    def get(self, request, *args, **kwargs):
        queryset = ChatgptAccount.objects.order_by("-id").all()
        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(chatgpt_username__icontains=query)
        status = request.query_params.get("status")
        if status in ("healthy", "unhealthy"):
            queryset = queryset.filter(auth_status=status == "healthy")
        pg = DefaultPageNumberPagination()
        pg.page_size_query_param = "page_size"
        page_accounts = pg.paginate_queryset(queryset, request=request)
        for account in page_accounts:
            try:
                account.refresh_auth_diagnostics()
            except Exception:
                pass
        serializer = ShowChatgptTokenSerializer(instance=page_accounts, many=True)
        return pg.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        # 兼容既有字段名；仅接受 Claude 网页 sessionKey 或 Cookie。
        serializer = AddChatgptTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        proxy_node_id = data.get("proxy_node_id")
        self._validate_proxy_node(proxy_node_id)

        for chatgpt_token in data["chatgpt_token_list"]:
            if not chatgpt_token:
                continue
            res_json = req_gateway("post", "/api/get-user-info", json={
                "chatgpt_token": chatgpt_token,
                "proxy_node_id": proxy_node_id,
            })
            res_json["auth_status"] = True
            res_json["proxy_node_id"] = proxy_node_id
            with transaction.atomic():
                ChatgptAccount.save_data(res_json)
                # 导入完成前，必须确认 Claude 上游记忆已关闭；失败则回滚本账号变更。
                chatgpt_name = res_json["user_info"]["email"]
                req_gateway("post", "/api/close-claude-memory", json={
                    "chatgpt_name": chatgpt_name,
                    "session_token": res_json.get("session_token"),
                    "extra_cookies": res_json.get("extra_cookies") or [],
                    "proxy_node_id": proxy_node_id,
                })

        return Response({"message": "录入成功"})

    def put(self, request):
        serializer = UpdateChatgptInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        queryset = ChatgptAccount.objects.filter(chatgpt_username=data["chatgpt_username"])
        account = queryset.first()
        proxy_node_id = data.get("proxy_node_id") if "proxy_node_id" in data else (
            account.proxy_node_id if account else None
        )
        self._validate_proxy_node(proxy_node_id)
        queryset.update(
            remark=data.get("remark") or "",
            proxy_node_id=proxy_node_id,
        )
        return Response({"message": "更新 Claude 账号信息成功"})

    def delete(self, request):
        serializer = DeleteChatgptAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gpt_obj = ChatgptAccount.objects.filter(chatgpt_username=serializer.data["chatgpt_username"]).first()
        if gpt_obj:
            car_obj = ChatgptCar.objects.filter(gpt_account_list=[gpt_obj.id], car_name__contains="reg_").first()
            if car_obj:
                User.objects.filter(gptcar_list=[car_obj.id]).delete()
                car_obj.delete()
            gpt_obj.delete()

        return Response({"message": "删除成功"})


class ChatGPTTokenExpiryView(APIView):
    permission_classes = (IsAuthenticated, IsAdminUser)

    def post(self, request):
        serializer = CheckChatgptTokenExpirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        queryset = ChatgptAccount.objects.order_by("-id").all()
        ids = serializer.data.get("ids") or []
        if ids:
            queryset = queryset.filter(id__in=ids)

        results = []
        for account in queryset:
            error = ""

            try:
                auth_state = account.refresh_auth_diagnostics(force=True)
            except Exception:
                error = "Claude 网页会话诊断失败"
                auth_state = None

            results.append(build_token_expiry_result(account, error=error, auth_state=auth_state))

        return Response({"results": results})


class ChatGPTRefreshTokenView(APIView):
    permission_classes = (IsAuthenticated, IsAdminUser)

    def post(self, request):
        serializer = RefreshChatgptTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raise ValidationError("Claude 网页会话不支持 RefreshToken；请重新录入 sessionKey 或 Cookie")


class ChatGPTLoginView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        if active_login_block_for(request.user):
            raise PermissionDenied("公告生效期间，暂不能进入 Claude Mirror")
        serializer = ChatGPTLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_gpt_list = ChatgptAccount.get_by_gptcar_list(request.user.gptcar_list)
        user_gpt_id_list = [i.id for i in user_gpt_list]

        # API/Web 仅保留为旧客户端兼容参数；两者均进入同一 Claude 网页会话。
        login_mode = "web"
        chatgpt_id = serializer.validated_data.get("chatgpt_id")
        if chatgpt_id is not None and chatgpt_id not in user_gpt_id_list:
            raise ValidationError("该账号不属于当前用户")

        if chatgpt_id is None:
            candidates = [
                item for item in user_gpt_list
                if item.auth_status and item.session_token_valid
            ]
            if not candidates:
                raise ValidationError("账号池中没有可用上游账号")
            chatgpt = min(candidates, key=lambda item: (item.login_count, item.id))
        else:
            chatgpt = ChatgptAccount.get_by_id(chatgpt_id)

        if login_mode == "web" and not chatgpt.session_token_valid:
            raise ValidationError("该账号当前不支持 Claude 网页会话，请联系管理员更新 sessionKey 或 Cookie")

        user_name = get_request_subject(request)
        payload = {
            "user_name": user_name,
            "authorization": gateway_authorization(request),
            "access_token": chatgpt.access_token,
            "session_token": chatgpt.session_token,
            "extra_cookies": chatgpt.extra_cookies,
            "login_mode": login_mode,
            "isolated_session": request.user.isolated_session,
            "mcp_isolation": request.user.mcp_isolation and request.user.capability_policy_initialized,
            "skills_isolation": request.user.skills_isolation and request.user.capability_policy_initialized,
            "mcp_allowed_ids": capability_aliases(request.user, "mcp_allowlist"),
            "skills_allowed_ids": capability_aliases(request.user, "skills_allowlist"),
            "limits": [
                item for item in (request.user.model_limit or []) if isinstance(item, str)
            ],
            "proxy_node_id": chatgpt.proxy_node_id,
            "daily_quota": request.user.daily_quota,
            "monthly_quota": request.user.monthly_quota,
            "force_chat_mode": request.user.force_chat_mode,
            "hide_chat_work_toggle": request.user.hide_chat_work_toggle,
            "hide_library": request.user.hide_library,
            "hide_suggestions": request.user.hide_suggestions,
        }
        payload.update(account_model_policy(request.user, chatgpt))
        # print(payload)
        res_json = req_gateway("post", "/api/login", json=payload)

        ChatgptAccount.objects.filter(id=chatgpt.id).update(login_count=F("login_count") + 1)

        save_visit_log(request, "choose-gpt", chatgpt.chatgpt_username)

        return Response(res_json)


class ChatGPTLoginCountResetView(APIView):
    permission_classes = (IsAuthenticated, IsAdminUser)

    def post(self, request):
        serializer = ResetChatgptLoginCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = ChatgptAccount.objects.filter(id=serializer.validated_data["id"]).update(login_count=0)
        if not updated:
            raise ValidationError("账号不存在")
        return Response({"message": "被登录次数已重置"})
