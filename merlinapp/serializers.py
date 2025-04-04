from rest_framework import serializers
from .models import FlightRecord

class FlightRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightRecord
        fields = '__all__'
