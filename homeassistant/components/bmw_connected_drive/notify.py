"""Support for BMW notifications."""
from __future__ import annotations

import logging
from typing import Any, cast

from bimmer_connected.vehicle import ConnectedDriveVehicle

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    BaseNotificationService,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LOCATION, ATTR_LONGITUDE, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as BMW_DOMAIN, BMWConnectedDriveAccount
from .const import CONF_ACCOUNT, DATA_ENTRIES

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
    accounts: list[BMWConnectedDriveAccount] = [
        e[CONF_ACCOUNT] for e in hass.data[BMW_DOMAIN][DATA_ENTRIES].values()
    ]
    _LOGGER.debug("Found BMW accounts: %s", ", ".join([a.name for a in accounts]))
    svc = BMWNotificationService()
    svc.setup(accounts)
    return svc


class BMWNotificationService(BaseNotificationService):
    """Send Notifications to BMW."""

    def __init__(self) -> None:
        """Set up the notification service."""
        self.targets: dict[str, ConnectedDriveVehicle] = {}

    def setup(self, accounts: list[BMWConnectedDriveAccount]) -> None:
        """Get the BMW vehicle(s) for the account(s)."""
        for account in accounts:
            self.targets.update({v.name: v for v in account.account.vehicles})

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message or POI to the car."""
        for vehicle in kwargs[ATTR_TARGET]:
            vehicle = cast(ConnectedDriveVehicle, vehicle)
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

                vehicle.remote_services.trigger_send_poi(location_dict)
            else:
                raise ValueError(f"'data.{ATTR_LOCATION}' is required.")
