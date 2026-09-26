from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from .models import CookRun, FireHearth, LaneGearLog, ResinLot, SoftPointProbe
from .services.floor_rules import assert_can_enter_drawing, assert_can_enter_ramping


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
                if (
                    phase == FireHearth.PHASE_RAMPING
                    and self.hearth.phase == FireHearth.PHASE_CHARGING
                ):
                    assert_can_enter_ramping(self.hearth)
                if phase == FireHearth.PHASE_DRAWING:
                    assert_can_enter_drawing(self.hearth)
            except DjangoValidationError as exc:
                # 服务层按 {"phase": [...]} 抛错；字段级 clean 需挂平铺消息
                raise forms.ValidationError(exc.messages)
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
        fields = ["lane", "switchedAt", "gear", "operatorName", "note"]
        widgets = {
            "lane": forms.NumberInput(attrs={"class": "field", "min": 1}),
            "switchedAt": forms.DateTimeInput(
                attrs={"class": "field", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "operatorName": forms.TextInput(attrs={"class": "field"}),
            "note": forms.TextInput(attrs={"class": "field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["switchedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.initial["switchedAt"] = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )

    def clean_switchedAt(self):
        switched_at = self.cleaned_data["switchedAt"]
        # 档志按分钟记：截断秒，与模型落库口径一致
        return switched_at.replace(second=0, microsecond=0)

    def clean(self):
        cleaned = super().clean()
        lane = cleaned.get("lane")
        switched_at = cleaned.get("switchedAt")
        if lane is not None and switched_at is not None:
            dup = LaneGearLog.objects.filter(lane=lane, switchedAt=switched_at)
            if self.instance and self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise forms.ValidationError(
                    f"过道 {lane} 在 "
                    f"{timezone.localtime(switched_at):%Y-%m-%d %H:%M} 已有档志，"
                    "同一过道同一分钟只留一条。"
                )
        return cleaned
