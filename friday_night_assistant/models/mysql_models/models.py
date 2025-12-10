from django.db import models


class AgentMemory(models.Model):
    """Simple key/value store for agent memory."""
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    value = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'mysql_models'
        verbose_name = 'Agent Memory'
        verbose_name_plural = 'Agent Memories'
        managed = True

    def __str__(self):
        return f"{self.id}"


class AgentTask(models.Model):
    """Task created by/for agents."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payload = models.JSONField(blank=True, null=True)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'mysql_models'
        verbose_name = 'Agent Task'
        verbose_name_plural = 'Agent Tasks'
        managed = True

    def __str__(self):
        return f"{self.name} ({self.status})"
