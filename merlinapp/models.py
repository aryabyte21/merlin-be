from django.db import models

class FlightRecord(models.Model):
    flight_number = models.CharField(max_length=10, null=True, blank=True)
    scheduled_arrival_time = models.DateTimeField(null=True, blank=True)
    actual_arrival_time = models.DateTimeField(null=True, blank=True)
    mawb = models.CharField(max_length=20, unique=True)
    flight_origin = models.CharField(max_length=10, null=True, blank=True)
    flight_destination = models.CharField(max_length=10, null=True, blank=True)
    pcs_awb = models.IntegerField(null=True, blank=True)
    pcs_received = models.IntegerField(null=True, blank=True)
    gross_weight = models.FloatField(null=True, blank=True)
    commodity_type = models.CharField(max_length=50, null=True, blank=True)
    discrepancy = models.BooleanField(default=False)
    bt_number = models.CharField(max_length=20, null=True, blank=True)
    timestamp_start = models.DateTimeField(null=True, blank=True)
    trolley_staff_id = models.CharField(max_length=50, null=True, blank=True)  # New field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.mawb} - {self.flight_number}"
