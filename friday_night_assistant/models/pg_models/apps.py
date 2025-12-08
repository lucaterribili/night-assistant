from django.apps import AppConfig


class PgModelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'friday_night_assistant.models.pg_models'
    label = 'pg_models'
    verbose_name = 'Postgres Models (not managed)'
