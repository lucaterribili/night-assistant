from django.contrib import admin
from .models import Post, Tutorial, Domain, Category


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_display', 'status', 'counter')
    search_fields = ('title',)

    def title_display(self, obj):
        if isinstance(obj.title, dict):
            return obj.title.get('en') or next(iter(obj.title.values()), '')
        return str(obj.title)

    title_display.short_description = 'title'


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_display', 'status', 'counter')
    search_fields = ('title',)

    def title_display(self, obj):
        if isinstance(obj.title, dict):
            return obj.title.get('en') or next(iter(obj.title.values()), '')
        return str(obj.title)

    title_display.short_description = 'title'


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
