"""Constants for the iaqualink component."""

from datetime import timedelta

DOMAIN = "iaqualink"

UPDATE_INTERVAL_BY_SYSTEM_TYPE: dict[str, timedelta] = {
    "iaqua": timedelta(seconds=15),
    "exo": timedelta(seconds=60),
}
UPDATE_INTERVAL_DEFAULT = timedelta(seconds=30)
