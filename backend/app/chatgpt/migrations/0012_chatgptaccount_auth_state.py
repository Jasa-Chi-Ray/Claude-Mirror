from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatgpt", "0011_account_health_notifications")]

    operations = [
        migrations.AddField(
            model_name="chatgptaccount",
            name="auth_state",
            field=models.CharField(default="unknown", max_length=8, verbose_name="Claude 诊断状态"),
        ),
    ]
