"""Support for BMW notifications."""
from __future__ import annotations

import logging
from typing import Any, cast

from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    BaseNotificationService,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LOCATION,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_ENTITY_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import BMWDataUpdateCoordinator

ATTR_LAT = "lat"
ATTR_LOCATION_ATTRIBUTES = ["street", "city", "postal_code", "country"]
ATTR_LON = "lon"
ATTR_SUBJECT = "subject"
ATTR_TEXT = "text"

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BMWNotificationService:
    """Get the BMW notification service."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][
        (discovery_info or {})[CONF_ENTITY_ID]
    ]

    targets = {}
    if not coordinator.read_only:
        targets.update({v.name: v for v in coordinator.account.vehicles})
    return BMWNotificationService(targets)


class BMWNotificationService(BaseNotificationService):
    """Send Notifications to BMW."""

    def __init__(self, targets: dict[str, MyBMWVehicle]) -> None:
        """Set up the notification service."""
        self.targets: dict[str, MyBMWVehicle] = targets

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message or POI to the car."""
        for vehicle in kwargs[ATTR_TARGET]:
            vehicle = cast(MyBMWVehicle, vehicle)
            _LOGGER.debug("Sending message to %s", vehicle.name)

            # Extract params from data dict
            data = kwargs.get(ATTR_DATA)

            # Check if message is a POI
            if data is not None and ATTR_LOCATION in data:
                location_dict = {
                    ATTR_LAT: data[ATTR_LOCATION][ATTR_LATITUDE],
                    ATTR_LON: data[ATTR_LOCATION][ATTR_LONGITUDE],
                    ATTR_NAME: message,
                }
                # Update dictionary with additional attributes if available
                location_dict.update(
                    {
                        k: v
                        for k, v in data[ATTR_LOCATION].items()
                        if k in ATTR_LOCATION_ATTRIBUTES
                    }
                )

                await vehicle.remote_services.trigger_send_poi(location_dict)
            else:
                raise ValueError(f"'data.{ATTR_LOCATION}' is required.")
