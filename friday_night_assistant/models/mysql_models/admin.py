from django.contrib import admin
from .models import AgentMemory, AgentTask


@admin.register(AgentMemory)
class AgentMemoryAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_at')
    search_fields = ('key',)


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'scheduled_for', 'updated_at')
    list_filter = ('status',)
    search_fields = ('name',)
