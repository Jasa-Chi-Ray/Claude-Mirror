from rest_framework import serializers

from app.chatgpt.models import ChatgptAccount, ChatgptCar
from app.utils import clean_int_list
import time

class ShowGptCarSerializer(serializers.ModelSerializer):
    gpt_account_name_list = serializers.SerializerMethodField()

    def get_gpt_account_name_list(self, obj):
        gpt_account_list = clean_int_list(obj.gpt_account_list)
        resutls = ChatgptAccount.objects.filter(id__in=gpt_account_list).values_list("chatgpt_username")
        return [i[0] for i in resutls]

    class Meta:
        model = ChatgptCar
        fields = "__all__"

class AddChatgptCarModelSerializer(serializers.ModelSerializer):

    def validate_empty_values(self, data):
        if not self.instance:
            data["created_time"] = int(time.time())

        data["updated_time"] = int(time.time())
        return (False, data)

    class Meta:
        model = ChatgptCar
        fields = "__all__"

class DeleteChatgptCarSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField())


class ShowChatgptTokenSerializer(serializers.ModelSerializer):
    access_token_exp = serializers.SerializerMethodField()
    expiry_status = serializers.SerializerMethodField()
    supported_login_modes = serializers.SerializerMethodField()
    has_refresh_token = serializers.SerializerMethodField()
    auth_state = serializers.SerializerMethodField()

    def get_access_token_exp(self, obj):
        # Claude 的 sessionKey 是不透明网页会话标识，不具备 JWT 的 exp 声明。
        return None

    def get_expiry_status(self, obj):
        return "unknown"

    def get_supported_login_modes(self, obj):
        return ["web"] if obj.session_token_valid else []

    def get_has_refresh_token(self, obj):
        return False

    def get_auth_state(self, obj):
        return obj.auth_state

    class Meta:
        model = ChatgptAccount
        fields = (
            "id",
            "chatgpt_username",
            "auth_status",
            "plan_type",
            "access_token_valid",
            "session_token_valid",
            "proxy_node_id",
            "last_check_at",
            "last_error",
            "auth_state",
            "remark",
            "created_time",
            "updated_time",
            "access_token_exp",
            "expiry_status",
            "login_count",
            "supported_login_modes",
            "has_refresh_token",
        )


class AddChatgptTokenSerializer(serializers.Serializer):
    auth_type = serializers.ChoiceField(choices=["cookie"], default="cookie", required=False)
    chatgpt_token_list = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)
    proxy_node_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs):
        if not attrs.get("chatgpt_token_list"):
            raise serializers.ValidationError({"chatgpt_token_list": "sessionKey 或 Cookie 列表不能为空"})
        return attrs

class CheckChatgptTokenExpirySerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=False)

class RefreshChatgptTokenSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class ResetChatgptLoginCountSerializer(serializers.Serializer):
    id = serializers.IntegerField()

class DeleteChatgptAccountSerializer(serializers.Serializer):
    chatgpt_username = serializers.CharField()

class UpdateChatgptInfoSerializer(serializers.Serializer):
    chatgpt_username = serializers.CharField()
    remark = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    proxy_node_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class ChatGPTLoginSerializer(serializers.Serializer):
    chatgpt_id = serializers.IntegerField(required=False, allow_null=True)
    login_mode = serializers.ChoiceField(choices=["api", "web"], default="api", required=False)
