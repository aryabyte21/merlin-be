from django.contrib import admin
from .models import FlightRecord

@admin.register(FlightRecord)
class FlightRecordAdmin(admin.ModelAdmin):
    list_display = ('mawb', 'flight_number', 'pcs_awb', 'pcs_received', 'discrepancy')
    search_fields = ('mawb', 'flight_number')
