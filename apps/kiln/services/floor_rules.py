"""灶台相位切换业务规则。"""
from decimal import Decimal

from django.core.exceptions import ValidationError

DRAWING_SOFT_POINT_MAX = Decimal("95")
RAMPING_GEAR_MIN = 3


def latest_lane_gear_log(lane: int):
    """该过道最新一条禁烟档志（按切换时刻倒序）。"""
    from apps.kiln.models import LaneGearLog

    return (
        LaneGearLog.objects.filter(lane=lane)
        .order_by("-switchedAt", "-id")
        .first()
    )


def record_lane_gear_log(*, lane, switchedAt, gear, operatorName, note=""):
    """
    登记过道禁烟档志。切换时刻截断到分钟；
    同一过道同一分钟只留一条，重复登记覆盖旧志。
    """
    from apps.kiln.models import LaneGearLog

    minute = switchedAt.replace(second=0, microsecond=0)
    log, _ = LaneGearLog.objects.update_or_create(
        lane=lane,
        switchedAt=minute,
        defaults={
            "gear": gear,
            "operatorName": operatorName,
            "note": note or "",
        },
    )
    return log


def assert_can_enter_ramping(hearth) -> None:
    """
    「装料 → 升温」前：该过道最新禁烟档志须
    档位 ≥ 3，且切换时刻不早于该灶当前值守的开灶时刻。
    """
    open_run = hearth.open_run()
    if open_run is None:
        raise ValidationError(
            {"phase": "无法进入升温：该灶没有进行中的值守纪录。"}
        )

    latest = latest_lane_gear_log(hearth.lane)
    if latest is None:
        raise ValidationError(
            {"phase": f"无法进入升温：过道 {hearth.lane} 尚无禁烟档志。"}
        )
    if latest.gear < RAMPING_GEAR_MIN:
        raise ValidationError(
            {
                "phase": (
                    f"无法进入升温：过道 {hearth.lane} 最新禁烟档志为 "
                    f"{latest.gear} 档，低于 {RAMPING_GEAR_MIN} 档。"
                )
            }
        )
    if latest.switchedAt < open_run.openedAt:
        raise ValidationError(
            {
                "phase": (
                    f"无法进入升温：过道 {hearth.lane} 最新档志切换于 "
                    f"{latest.switchedAt:%Y-%m-%d %H:%M}，早于本值守开灶时刻 "
                    f"{open_run.openedAt:%Y-%m-%d %H:%M}，请重新登记档志。"
                )
            }
        )


def assert_can_enter_drawing(hearth) -> None:
    """
    进入「出胶」相位前：当前未收灶的 CookRun 须至少有一条
    softPointC <= 95 的 SoftPointProbe。
    """
    open_run = hearth.open_run()
    if open_run is None:
        raise ValidationError(
            {"phase": "无法进入出胶：该灶没有进行中的值守纪录。"}
        )

    ok = open_run.probes.filter(softPointC__lte=DRAWING_SOFT_POINT_MAX).exists()
    if not ok:
        raise ValidationError(
            {
                "phase": (
                    "无法进入出胶：进行中值守尚无软化点探针 "
                    f"≤ {DRAWING_SOFT_POINT_MAX}℃。"
                )
            }
        )


def change_hearth_phase(hearth, new_phase: str):
    """统一入口：改相位时校验升温 / 出胶规则并保存。"""
    from apps.kiln.models import FireHearth

    if new_phase == FireHearth.PHASE_DRAWING:
        assert_can_enter_drawing(hearth)
    elif (
        new_phase == FireHearth.PHASE_RAMPING
        and hearth.phase == FireHearth.PHASE_CHARGING
    ):
        assert_can_enter_ramping(hearth)

    hearth.phase = new_phase
    hearth.save(update_fields=["phase"])
    return hearth
