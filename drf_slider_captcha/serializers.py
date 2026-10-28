import math

from rest_framework import serializers

from .conf import get_config


class FiniteFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        if isinstance(data, bool):
            self.fail("invalid")
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            self.fail("invalid")
        return value


class ChallengeSerializer(serializers.Serializer):
    purpose = serializers.ChoiceField(choices=(), default="login")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purpose"].choices = get_config().PURPOSES
        self.fields["purpose"].default = get_config().PURPOSES[0]


class VerifySerializer(serializers.Serializer):
    challengeId = serializers.UUIDField()
    x = FiniteFloatField(min_value=0, max_value=1024)
    duration = serializers.IntegerField(min_value=0, max_value=3_600_000)
    y = FiniteFloatField(required=False, min_value=-10000, max_value=10000)
    sliderOffsetX = FiniteFloatField(required=False, min_value=0, max_value=10000)
    trail = serializers.ListField(
        child=serializers.ListField(child=FiniteFloatField(min_value=-10000, max_value=10000),
                                   min_length=2, max_length=2),
        required=False, max_length=512,
    )
    targetType = serializers.ChoiceField(choices=("puzzle", "button"), required=False)
    errorCount = serializers.IntegerField(min_value=0, max_value=100000, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["trail"].max_length = get_config().MAX_TRAIL_POINTS
