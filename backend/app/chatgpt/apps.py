from django.apps import AppConfig


class ChatgptConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.chatgpt"
    label = "chatgpt"
    verbose_name = "Claude"
