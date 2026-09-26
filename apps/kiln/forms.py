from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import CookRun, FireHearth, LaneGearLog, ResinLot, SoftPointProbe
from .services.floor_rules import (
    RAMPING_GEAR_MIN,
    assert_can_enter_drawing,
    assert_can_enter_ramping,
)


class ResinLotForm(forms.ModelForm):
    class Meta:
        model = ResinLot
        fields = ["lotCode", "originPlace", "arrivalKg", "receivedAt"]
        widgets = {
            "lotCode": forms.TextInput(attrs={"class": "field"}),
            "originPlace": forms.TextInput(attrs={"class": "field"}),
            "arrivalKg": forms.NumberInput(attrs={"class": "field", "step": "0.01"}),
            "receivedAt": forms.DateTimeInput(
                attrs={"class": "field", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["receivedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if self.instance and self.instance.pk and self.instance.receivedAt:
            local = timezone.localtime(self.instance.receivedAt)
            self.initial["receivedAt"] = local.strftime("%Y-%m-%dT%H:%M")


class PhaseChangeForm(forms.Form):
    phase = forms.ChoiceField(
        label="相位",
        choices=FireHearth.PHASE_CHOICES,
        widget=forms.Select(attrs={"class": "field"}),
    )

    def __init__(self, *args, hearth=None, **kwargs):
        self.hearth = hearth
        super().__init__(*args, **kwargs)
        if hearth is not None and not self.is_bound:
            self.fields["phase"].initial = hearth.phase

    def clean_phase(self):
        phase = self.cleaned_data["phase"]
        if self.hearth is not None:
            try:
                if phase == FireHearth.PHASE_DRAWING:
                    assert_can_enter_drawing(self.hearth)
                elif (
                    phase == FireHearth.PHASE_RAMPING
                    and self.hearth.phase == FireHearth.PHASE_CHARGING
                ):
                    assert_can_enter_ramping(self.hearth)
            except ValidationError as exc:
                # 服务层抛的是 {"phase": [...]} 字典，字段级 clean 须摊平再抛
                raise ValidationError(exc.messages)
        return phase


class SoftPointProbeForm(forms.ModelForm):
    class Meta:
        model = SoftPointProbe
        fields = ["sampledAt", "softPointC", "samplerName"]
        widgets = {
            "sampledAt": forms.DateTimeInput(
                attrs={"class": "field", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "softPointC": forms.NumberInput(attrs={"class": "field", "step": "0.01"}),
            "samplerName": forms.TextInput(attrs={"class": "field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sampledAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.initial["sampledAt"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")


class OpenCookRunForm(forms.ModelForm):
    class Meta:
        model = CookRun
        fields = ["resinLot", "openedAt", "targetSoftPointC"]
        widgets = {
            "resinLot": forms.Select(attrs={"class": "field"}),
            "openedAt": forms.DateTimeInput(
                attrs={"class": "field", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "targetSoftPointC": forms.NumberInput(
                attrs={"class": "field", "step": "0.01"}
            ),
        }

    def __init__(self, *args, hearth=None, **kwargs):
        self.hearth = hearth
        super().__init__(*args, **kwargs)
        self.fields["openedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        self.fields["resinLot"].queryset = ResinLot.objects.all()
        if not self.is_bound:
            self.initial["openedAt"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        if self.hearth is not None and self.hearth.open_run() is not None:
            raise forms.ValidationError("该灶已有进行中的值守，请先收灶再开新灶。")
        return cleaned


class LaneGearLogForm(forms.ModelForm):
    class Meta:
        model = LaneGearLog
        fields = ["switchedAt", "gear", "operatorName", "note"]
        widgets = {
            "switchedAt": forms.DateTimeInput(
                attrs={"class": "field", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "gear": forms.Select(
                choices=[
                    (g, f"{g} 档")
                    for g in range(LaneGearLog.GEAR_MIN, LaneGearLog.GEAR_MAX + 1)
                ],
                attrs={"class": "field"},
            ),
            "operatorName": forms.TextInput(attrs={"class": "field"}),
            "note": forms.TextInput(
                attrs={"class": "field", "placeholder": "可空"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["switchedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if not self.is_bound:
            self.initial["switchedAt"] = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )
            self.initial["gear"] = RAMPING_GEAR_MIN
            if user is not None and user.is_authenticated:
                self.initial["operatorName"] = user.username
