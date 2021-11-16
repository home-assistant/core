"""Constants for the pi_hole integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import PERCENTAGE

DOMAIN = "pi_hole"

CONF_LOCATION = "location"
CONF_STATISTICS_ONLY = "statistics_only"

DEFAULT_LOCATION = "admin"
DEFAULT_METHOD = "GET"
DEFAULT_NAME = "Pi-Hole"
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_STATISTICS_ONLY = True

SERVICE_DISABLE = "disable"
SERVICE_DISABLE_ATTR_DURATION = "duration"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

DATA_KEY_API = "api"
DATA_KEY_COORDINATOR = "coordinator"


@dataclass
class PiHoleSensorEntityDescription(SensorEntityDescription):
    """Describes PiHole sensor entity."""

    icon: str = "mdi:pi-hole"


SENSOR_TYPES: tuple[PiHoleSensorEntityDescription, ...] = (
    PiHoleSensorEntityDescription(
        key="ads_blocked_today",
        name="Ads Blocked Today",
        native_unit_of_measurement="ads",
        icon="mdi:close-octagon-outline",
    ),
    PiHoleSensorEntityDescription(
        key="ads_percentage_today",
        name="Ads Percentage Blocked Today",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:close-octagon-outline",
    ),
    PiHoleSensorEntityDescription(
        key="clients_ever_seen",
        name="Seen Clients",
        native_unit_of_measurement="clients",
        icon="mdi:account-outline",
    ),
    PiHoleSensorEntityDescription(
        key="dns_queries_today",
        name="DNS Queries Today",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    PiHoleSensorEntityDescription(
        key="domains_being_blocked",
        name="Domains Blocked",
        native_unit_of_measurement="domains",
        icon="mdi:block-helper",
    ),
    PiHoleSensorEntityDescription(
        key="queries_cached",
        name="DNS Queries Cached",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    PiHoleSensorEntityDescription(
        key="queries_forwarded",
        name="DNS Queries Forwarded",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    PiHoleSensorEntityDescription(
        key="unique_clients",
        name="DNS Unique Clients",
        native_unit_of_measurement="clients",
        icon="mdi:account-outline",
    ),
    PiHoleSensorEntityDescription(
        key="unique_domains",
        name="DNS Unique Domains",
        native_unit_of_measurement="domains",
        icon="mdi:domain",
    ),
)
