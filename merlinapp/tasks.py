from celery import shared_task
from .views import merge_data
from django.http import HttpRequest

@shared_task
def scheduled_data_merge():
    """Task to periodically call the merge_data function"""
    request = HttpRequest()
    merge_data(request)
    return "Data merge completed successfully"