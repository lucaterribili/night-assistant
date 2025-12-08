from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Post(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.JSONField()  # jsonb in Postgres migration
    status = models.CharField(max_length=50, blank=True, null=True)
    body = models.JSONField(blank=True, null=True)  # jsonb in migration
    counter = models.IntegerField(default=0)

    class Meta:
        app_label = 'pg_models'
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        managed = False  # non gestito da Django
        db_table = 'posts'

    def __str__(self):
        # try to show a readable title if it's a dict with 'en' or fallback
        if isinstance(self.title, dict):
            return self.title.get('en') or next(iter(self.title.values()), '')
        return str(self.title)


class Tutorial(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.JSONField()
    status = models.CharField(max_length=50, blank=True, null=True)
    body = models.JSONField(blank=True, null=True)
    counter = models.IntegerField(default=0)

    class Meta:
        app_label = 'pg_models'
        verbose_name = 'Tutorial'
        verbose_name_plural = 'Tutorials'
        managed = False
        db_table = 'tutorials'

    def __str__(self):
        if isinstance(self.title, dict):
            return self.title.get('en') or next(iter(self.title.values()), '')
        return str(self.title)


class Domain(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        app_label = 'pg_models'
        verbose_name = 'Domain'
        verbose_name_plural = 'Domains'
        managed = False
        db_table = 'domains'

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    class Meta:
        app_label = 'pg_models'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        managed = False
        db_table = 'categories'

    def __str__(self):
        return self.name


# Polymorphic "morph" style tables using contenttypes
class Categorizable(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.BigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        app_label = 'pg_models'
        verbose_name = 'Categorizable'
        verbose_name_plural = 'Categorizables'
        managed = False
        db_table = 'categorizables'


class Dominable(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.BigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        app_label = 'pg_models'
        verbose_name = 'Dominable'
        verbose_name_plural = 'Dominables'
        managed = False
        db_table = 'dominables'
