from .views import lane_gear_map


def lane_gear_strip(request):
    """班次条挂各过道最新禁烟档位。"""
    if not request.user.is_authenticated:
        return {}
    gears = lane_gear_map()
    return {"strip_lane_gears": [gears[lane] for lane in sorted(gears)]}
