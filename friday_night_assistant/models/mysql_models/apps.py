from django.apps import AppConfig


class MysqlModelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'friday_night_assistant.models.mysql_models'
    label = 'mysql_models'
    verbose_name = 'MySQL Models (managed)'
