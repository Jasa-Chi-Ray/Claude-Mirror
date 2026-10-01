import time

from django.db import models
from app.fields import EncryptedJSONField, EncryptedTextField
from django.utils import timezone


class AccountHealthSettings(models.Model):
    # One installation-wide configuration; secrets never appear in API responses.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=False)
    interval_minutes = models.PositiveIntegerField(default=5)
    recipient = models.EmailField(blank=True)
    smtp_host = models.CharField(max_length=253, blank=True)
    smtp_port = models.PositiveIntegerField(default=465)
    smtp_security = models.CharField(max_length=8, default="ssl")
    smtp_username = models.EmailField(blank=True)
    smtp_password = EncryptedTextField(blank=True, default="")
    imap_host = models.CharField(max_length=253, blank=True)
    imap_port = models.PositiveIntegerField(default=993)
    imap_security = models.CharField(max_length=8, default="ssl")
    imap_username = models.CharField(max_length=254, blank=True)
    imap_password = EncryptedTextField(blank=True, default="")
    revision = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_mail_error = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Claude 账号健康设置"
        verbose_name_plural = "Claude 账号健康设置"


class ChatgptCar(models.Model):
    car_name = models.CharField(unique=True, max_length=32, verbose_name="Claude 账号池名称")
    remark = models.CharField(max_length=128, blank=True, verbose_name="备注")
    gpt_account_list = models.JSONField(default=list, verbose_name="Claude 账号列表")
    created_time = models.IntegerField(db_index=True, blank=True, verbose_name="创建时间")
    updated_time = models.IntegerField(db_index=True, blank=True, verbose_name="最后修改时间")

    class Meta:
        verbose_name = "Claude 账号池"
        verbose_name_plural = "Claude 账号池"

class ChatgptAccount(models.Model):
    AUTH_STATES = ("valid", "invalid", "unknown")
    chatgpt_username = models.CharField(max_length=64, unique=True, verbose_name="Claude 账号")
    auth_status = models.BooleanField(default=True, verbose_name="Claude 授权状态")
    plan_type = models.CharField(max_length=32, verbose_name="Claude 套餐")
    access_token = EncryptedTextField(verbose_name="Claude 会话凭据")
    session_token = EncryptedTextField(null=True, blank=True, verbose_name="Claude 网页会话凭据")
    extra_cookies = EncryptedJSONField(default=list, blank=True, verbose_name="额外 Cookie")
    refresh_token = EncryptedTextField(null=True, blank=True, verbose_name="旧刷新凭据（兼容保留）")
    refresh_client_id = EncryptedTextField(null=True, blank=True, verbose_name="旧刷新客户端标识（兼容保留）")
    access_token_valid = models.BooleanField(default=False, verbose_name="Claude 会话可用")
    session_token_valid = models.BooleanField(default=False, verbose_name="Claude 网页会话可用")
    auth_state = models.CharField(max_length=8, default="unknown", verbose_name="Claude 诊断状态")
    proxy_node_id = models.IntegerField(null=True, blank=True, verbose_name="代理节点")
    last_check_at = models.IntegerField(null=True, blank=True, verbose_name="最近诊断时间")
    last_error = models.TextField(null=True, blank=True, verbose_name="最近诊断错误")
    login_count = models.PositiveBigIntegerField(default=0, verbose_name="被登录次数")
    remark = models.TextField(null=True, blank=True,verbose_name="备注")
    created_time = models.IntegerField(db_index=True, blank=True, verbose_name="创建时间")
    updated_time = models.IntegerField(db_index=True, blank=True, verbose_name="最后修改时间")

    class Meta:
        verbose_name = "Claude 上游账号"
        verbose_name_plural = "Claude 上游账号"

    @classmethod
    def get_by_gptcar_list(cls, gptcar_list):
        if not gptcar_list:
            return cls.objects.none()

        chatgpt_account_list = []
        for line in ChatgptCar.objects.filter(id__in=gptcar_list).values("gpt_account_list"):
            chatgpt_account_list.extend(line["gpt_account_list"])

        return cls.objects.filter(id__in=chatgpt_account_list).order_by("-plan_type", "-id")


    @classmethod
    def get_by_id(cls, chatgpt_id):
        return cls.objects.filter(id=chatgpt_id).first()

    def refresh_auth_diagnostics(self, force=False):
        now = int(time.time())
        if not force and self.last_check_at and now - self.last_check_at < 3600:
            return self.auth_state

        from app.utils import req_gateway

        result = req_gateway("post", "/api/diagnose-claude-auth", json={
            "access_token": self.access_token,
            "session_token": self.session_token,
            "extra_cookies": self.extra_cookies,
            "proxy_node_id": self.proxy_node_id,
        })
        auth_state = result.get("auth_state")
        if auth_state == "unknown":
            # 网络或验证挑战无法确定会话状态时，不能把既有的有效状态误写成失效。
            self.auth_state = "unknown"
        else:
            # 兼容仍返回旧布尔字段的网关版本。
            self.access_token_valid = bool(result.get("access_token_valid"))
            self.session_token_valid = bool(result.get("session_token_valid"))
            self.auth_state = auth_state if auth_state in self.AUTH_STATES else (
                "valid" if self.session_token_valid else "invalid"
            )
        self.last_check_at = result.get("last_check_at") or now
        self.last_error = result.get("last_error") or (
            "Claude 网页会话暂不可验证" if auth_state == "unknown" else ""
        )

        if auth_state != "unknown":
            user_info = result.get("user_info") or {}
            if user_info.get("email"):
                self.chatgpt_username = user_info["email"]
            if user_info.get("plan_type"):
                self.plan_type = user_info["plan_type"]

        self.updated_time = now
        self.save(update_fields=[
            "chatgpt_username",
            "plan_type",
            "access_token_valid",
            "session_token_valid",
            "auth_state",
            "last_check_at",
            "last_error",
            "updated_time",
        ])
        return self.auth_state

    @classmethod
    def save_data(cls, data):
        obj = cls.objects.filter(chatgpt_username=data["user_info"]["email"]).first()
        new_obj = obj or cls()
        new_obj.chatgpt_username = data["user_info"]["email"]
        new_obj.plan_type = data["user_info"]["plan_type"]
        new_obj.access_token = data["access_token"]

        if data.get("auth_status") is not None:
            new_obj.auth_status = data["auth_status"]

        new_obj.session_token = data.get("session_token") or data["access_token"]
        # 保留字段只为既有数据库兼容；Claude 网页会话不支持 RefreshToken。
        new_obj.refresh_token = None
        new_obj.refresh_client_id = None

        if data.get("extra_cookies") is not None:
            new_obj.extra_cookies = data.get("extra_cookies") or []

        if "proxy_node_id" in data:
            new_obj.proxy_node_id = data["proxy_node_id"]

        auth_state = data.get("auth_state")
        if auth_state not in cls.AUTH_STATES:
            auth_state = "valid" if data.get("session_token_valid") else "invalid"
        new_obj.auth_state = auth_state
        if auth_state != "unknown":
            new_obj.access_token_valid = bool(data.get("access_token_valid"))
            new_obj.session_token_valid = bool(data.get("session_token_valid"))
        new_obj.last_check_at = data.get("last_check_at") or int(time.time())
        new_obj.last_error = data.get("last_error") or ""

        new_obj.updated_time = int(time.time())

        if not obj:
            new_obj.created_time = int(time.time())

        new_obj.save()
        return new_obj.id


class AccountHealthState(models.Model):
    account = models.OneToOneField(ChatgptAccount, on_delete=models.CASCADE)
    next_check_at = models.DateTimeField(default=timezone.now, db_index=True)
    first_failure_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    notified = models.BooleanField(default=False)
    detail = models.CharField(max_length=200, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    lease_token = models.CharField(max_length=32, blank=True)

    class Meta:
        verbose_name = "Claude 账号健康状态"
        verbose_name_plural = "Claude 账号健康状态"
