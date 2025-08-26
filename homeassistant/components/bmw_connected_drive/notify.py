"""Support for BMW notifications."""

from __future__ import annotations

import logging
from typing import Any, cast

from bimmer_connected.models import MyBMWAPIError, PointOfInterest
from bimmer_connected.vehicle import MyBMWVehicle
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    BaseNotificationService,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, BMWConfigEntry

PARALLEL_UPDATES = 1

ATTR_LOCATION_ATTRIBUTES = ["street", "city", "postal_code", "country"]

POI_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
        vol.Optional("street"): cv.string,
        vol.Optional("city"): cv.string,
        vol.Optional("postal_code"): cv.string,
        vol.Optional("country"): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BMWNotificationService:
    """Get the BMW notification service."""
    config_entry: BMWConfigEntry | None = hass.config_entries.async_get_entry(
        (discovery_info or {})[CONF_ENTITY_ID]
    )

    targets = {}
    if (
        config_entry
        and (coordinator := config_entry.runtime_data)
        and not coordinator.read_only
    ):
        targets.update({v.name: v for v in coordinator.account.vehicles})
    return BMWNotificationService(targets)


class BMWNotificationService(BaseNotificationService):
    """Send Notifications to BMW."""

    vehicle_targets: dict[str, MyBMWVehicle]

    def __init__(self, targets: dict[str, MyBMWVehicle]) -> None:
        """Set up the notification service."""
        self.vehicle_targets = targets

    @property
    def targets(self) -> dict[str, Any] | None:
        """Return a dictionary of registered targets."""
        return self.vehicle_targets

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message or POI to the car."""

        try:
            # Verify data schema
            poi_data = kwargs.get(ATTR_DATA) or {}
            POI_SCHEMA(poi_data)

            # Create the POI object
            poi = PointOfInterest(
                lat=poi_data.pop(ATTR_LATITUDE),
                lon=poi_data.pop(ATTR_LONGITUDE),
                name=(message or None),
                **poi_data,
            )

        except (vol.Invalid, TypeError, ValueError) as ex:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_poi",
                translation_placeholders={
                    "poi_exception": str(ex),
                },
            ) from ex

        for vehicle in kwargs[ATTR_TARGET]:
            vehicle = cast(MyBMWVehicle, vehicle)
            _LOGGER.debug("Sending message to %s", vehicle.name)

            try:
                await vehicle.remote_services.trigger_send_poi(poi)
            except MyBMWAPIError as ex:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="remote_service_error",
                    translation_placeholders={"exception": str(ex)},
                ) from ex
