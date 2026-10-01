import app.fields
from django.db import migrations, models


def _set_permission_labels(apps, schema_editor, labels):
    permission = apps.get_model("auth", "Permission")
    for model, label in labels.items():
        for action in ("add", "change", "delete", "view"):
            permission.objects.using(schema_editor.connection.alias).filter(
                content_type__app_label="chatgpt", content_type__model=model,
                codename=f"{action}_{model}",
            ).update(name=f"Can {action} {label}")


def rename_permission_labels(apps, schema_editor):
    _set_permission_labels(apps, schema_editor, {
        "chatgptaccount": "Claude 上游账号", "chatgptcar": "Claude 账号池",
        "accounthealthsettings": "Claude 账号健康设置", "accounthealthstate": "Claude 账号健康状态",
    })


def restore_permission_labels(apps, schema_editor):
    _set_permission_labels(apps, schema_editor, {
        "chatgptaccount": "chatgpt account", "chatgptcar": "chatgpt car",
        "accounthealthsettings": "account health settings", "accounthealthstate": "account health state",
    })


class Migration(migrations.Migration):
    dependencies = [("chatgpt", "0012_chatgptaccount_auth_state"), ("auth", "0012_alter_user_first_name_max_length")]

    operations = [
        migrations.AlterModelOptions(
            name="accounthealthsettings",
            options={"verbose_name": "Claude 账号健康设置", "verbose_name_plural": "Claude 账号健康设置"},
        ),
        migrations.AlterModelOptions(
            name="accounthealthstate",
            options={"verbose_name": "Claude 账号健康状态", "verbose_name_plural": "Claude 账号健康状态"},
        ),
        migrations.AlterModelOptions(
            name="chatgptaccount",
            options={"verbose_name": "Claude 上游账号", "verbose_name_plural": "Claude 上游账号"},
        ),
        migrations.AlterModelOptions(
            name="chatgptcar",
            options={"verbose_name": "Claude 账号池", "verbose_name_plural": "Claude 账号池"},
        ),
        migrations.AlterField(
            model_name="chatgptcar",
            name="car_name",
            field=models.CharField(max_length=32, unique=True, verbose_name="Claude 账号池名称"),
        ),
        migrations.AlterField(
            model_name="chatgptcar",
            name="gpt_account_list",
            field=models.JSONField(default=list, verbose_name="Claude 账号列表"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="chatgpt_username",
            field=models.CharField(max_length=64, unique=True, verbose_name="Claude 账号"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="auth_status",
            field=models.BooleanField(default=True, verbose_name="Claude 授权状态"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="plan_type",
            field=models.CharField(max_length=32, verbose_name="Claude 套餐"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="access_token",
            field=app.fields.EncryptedTextField(verbose_name="Claude 会话凭据"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="session_token",
            field=app.fields.EncryptedTextField(blank=True, null=True, verbose_name="Claude 网页会话凭据"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="refresh_token",
            field=app.fields.EncryptedTextField(blank=True, null=True, verbose_name="旧刷新凭据（兼容保留）"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="refresh_client_id",
            field=app.fields.EncryptedTextField(blank=True, null=True, verbose_name="旧刷新客户端标识（兼容保留）"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="access_token_valid",
            field=models.BooleanField(default=False, verbose_name="Claude 会话可用"),
        ),
        migrations.AlterField(
            model_name="chatgptaccount",
            name="session_token_valid",
            field=models.BooleanField(default=False, verbose_name="Claude 网页会话可用"),
        ),
        migrations.RunPython(rename_permission_labels, restore_permission_labels),
    ]
