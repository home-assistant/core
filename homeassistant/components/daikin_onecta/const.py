"""Constants for Daikin Onecta."""

from typing import NamedTuple

DOMAIN = "daikin_onecta"

OAUTH2_AUTHORIZE = "https://idp.onecta.daikineurope.com/v1/oidc/authorize"
OAUTH2_TOKEN = "https://idp.onecta.daikineurope.com/v1/oidc/token"

FANMODE_FIXED = "fixed"


class EnergyPeriod(NamedTuple):
    """Home Assistant labels and ID suffixes for Daikin energy periods."""

    label: str
    unique_id_suffix: str


ENERGY_AGGREGATE_PERIODS: dict[str, EnergyPeriod] = {
    "day": EnergyPeriod("Daily", "daily"),
    "week": EnergyPeriod("Weekly", "weekly"),
    "year": EnergyPeriod("Yearly", "yearly"),
    "month": EnergyPeriod("Monthly", "monthly"),
}
