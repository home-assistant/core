"""Constants used by the Withings component."""
import logging

from aiowithings import WorkoutCategory

LOGGER = logging.getLogger(__package__)

DEFAULT_TITLE = "Withings"
CONF_PROFILES = "profiles"
CONF_USE_WEBHOOK = "use_webhook"

DOMAIN = "withings"

SCORE_POINTS = "points"
UOM_BEATS_PER_MINUTE = "bpm"
UOM_BREATHS_PER_MINUTE = "br/min"
UOM_FREQUENCY = "times"
UOM_MMHG = "mmhg"

WORKOUT_CATEGORY: dict[WorkoutCategory, str] = {
    WorkoutCategory.WALK: "walk",
    WorkoutCategory.RUN: "run",
    WorkoutCategory.HIKING: "hiking",
    WorkoutCategory.SKATING: "skating",
    WorkoutCategory.BMX: "bmx",
    WorkoutCategory.BICYCLING: "bicycling",
    WorkoutCategory.SWIMMING: "swimming",
    WorkoutCategory.SURFING: "surfing",
    WorkoutCategory.KITESURFING: "kitesurfing",
    WorkoutCategory.WINDSURFING: "windsurfing",
    WorkoutCategory.BODYBOARD: "bodyboard",
    WorkoutCategory.TENNIS: "tennis",
    WorkoutCategory.TABLE_TENNIS: "table_tennis",
    WorkoutCategory.SQUASH: "squash",
    WorkoutCategory.BADMINTON: "badminton",
    WorkoutCategory.LIFT_WEIGHTS: "lift_weights",
    WorkoutCategory.CALISTHENICS: "calisthenics",
    WorkoutCategory.ELLIPTICAL: "elliptical",
    WorkoutCategory.PILATES: "pilates",
    WorkoutCategory.BASKET_BALL: "basket_ball",
    WorkoutCategory.SOCCER: "soccer",
    WorkoutCategory.FOOTBALL: "football",
    WorkoutCategory.VOLLEY_BALL: "volley_ball",
    WorkoutCategory.WATERPOLO: "waterpolo",
    WorkoutCategory.HORSE_RIDING: "horse_riding",
    WorkoutCategory.GOLF: "golf",
    WorkoutCategory.YOGA: "yoga",
    WorkoutCategory.DANCING: "dancing",
    WorkoutCategory.BOXING: "boxing",
    WorkoutCategory.FENCING: "fencing",
    WorkoutCategory.WRESTLING: "wrestling",
    WorkoutCategory.MARTIAL_ARTS: "martial_arts",
    WorkoutCategory.SKIING: "skiing",
    WorkoutCategory.SNOWBOARDING: "snowboarding",
    WorkoutCategory.OTHER: "other",
    WorkoutCategory.NO_ACTIVITY: "no_activity",
    WorkoutCategory.ROWING: "rowing",
    WorkoutCategory.ZUMBA: "zumba",
    WorkoutCategory.BASEBALL: "baseball",
    WorkoutCategory.HANDBALL: "handball",
    WorkoutCategory.HOCKEY: "hockey",
    WorkoutCategory.ICE_HOCKEY: "ice_hockey",
    WorkoutCategory.CLIMBING: "climbing",
    WorkoutCategory.ICE_SKATING: "ice_skating",
    WorkoutCategory.MULTI_SPORT: "multi_sport",
    WorkoutCategory.INDOOR_WALK: "indoor_walk",
    WorkoutCategory.INDOOR_RUNNING: "indoor_running",
    WorkoutCategory.INDOOR_CYCLING: "indoor_cycling",
}
