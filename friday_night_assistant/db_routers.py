"""
Simple DB router: route `mysql_models` app to `default` (MySQL)
and `pg_models` app to `postgres` (Postgres).
"""

class DatabaseAppsRouter:
    """A router to control all database operations on models in
    the mysql_models and pg_models applications.

    - mysql_models -> 'default'
    - pg_models -> 'postgres'
    """

    mysql_apps = {'mysql_models'}
    pg_apps = {'pg_models'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.mysql_apps:
            return 'default'
        if model._meta.app_label in self.pg_apps:
            return 'postgres'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.mysql_apps:
            return 'default'
        if model._meta.app_label in self.pg_apps:
            return 'postgres'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations if both objects are in the same routed app group
        if obj1._meta.app_label in self.mysql_apps and obj2._meta.app_label in self.mysql_apps:
            return True
        if obj1._meta.app_label in self.pg_apps and obj2._meta.app_label in self.pg_apps:
            return True
        # No cross-db relations
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure the mysql_models app's models appear only in the 'default' DB
        and pg_models in the 'postgres' DB. For apps not listed, allow migrations on default.
        """
        if app_label in self.mysql_apps:
            return db == 'default'
        if app_label in self.pg_apps:
            # pg_models we set managed = False on their models, so typically return False
            # but allow migrations on postgres if you decide to manage them with Django
            return db == 'postgres'
        # Default behaviour
        return db == 'default'

