"""Constants for the Formula 1 integration."""

from datetime import timedelta

DOMAIN = "formula_one"

DEFAULT_UPDATE_INTERVAL = timedelta(hours=1)

F1_STATE_UNAVAILABLE = "(unavailable)"
F1_STATE_MULTIPLE = "(multiple)"

F1_DISCOVERY_NEW = "f1_discovery_new"

F1_CONSTRUCTOR_ATTRIBS_UNAVAILABLE = {
    "points": F1_STATE_UNAVAILABLE,
    "nationality": F1_STATE_UNAVAILABLE,
    "constructor_id": F1_STATE_UNAVAILABLE,
    "season": F1_STATE_UNAVAILABLE,
    "round": F1_STATE_UNAVAILABLE,
    "position": F1_STATE_UNAVAILABLE,
}

F1_DRIVER_ATTRIBS_UNAVAILABLE = {
    "points": F1_STATE_UNAVAILABLE,
    "nationality": F1_STATE_UNAVAILABLE,
    "team": F1_STATE_UNAVAILABLE,
    "driver_id": F1_STATE_UNAVAILABLE,
    "season": F1_STATE_UNAVAILABLE,
    "round": F1_STATE_UNAVAILABLE,
    "position": F1_STATE_UNAVAILABLE,
}

F1_RACE_ATTRIBS_UNAVAILABLE = {
    "season": F1_STATE_UNAVAILABLE,
    "round": F1_STATE_UNAVAILABLE,
    "start": F1_STATE_UNAVAILABLE,
    "fp1_start": F1_STATE_UNAVAILABLE,
    "fp2_start": F1_STATE_UNAVAILABLE,
    "fp3_start": F1_STATE_UNAVAILABLE,
    "quali_start": F1_STATE_UNAVAILABLE,
    "sprint_start": F1_STATE_UNAVAILABLE,
}
