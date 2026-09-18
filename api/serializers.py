from rest_framework import serializers

class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(required=True, help_text="Start location within the USA")
    finish = serializers.CharField(required=True, help_text="Finish location within the USA")
    
    def validate(self, data):
        if data['start'].strip().lower() == data['finish'].strip().lower():
            raise serializers.ValidationError("Start and finish locations cannot be identical.")
        return data
