from django.contrib import admin
from .models import AgentMemory, AgentTask


@admin.register(AgentMemory)
class AgentMemoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'key', 'updated_at')
    search_fields = ('id', 'key')


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'scheduled_for', 'updated_at')
    list_filter = ('status',)
    search_fields = ('name',)
