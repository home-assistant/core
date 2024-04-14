"""Support for Ecobee Send Message service."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from homeassistant.components.notify import (
    ATTR_TARGET,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import Ecobee, EcobeeData
from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> EcobeeNotificationService | None:
    """Get the Ecobee notification service."""
    if discovery_info is None:
        return None

    data: EcobeeData = hass.data[DOMAIN]
    return EcobeeNotificationService(data.ecobee)


class EcobeeNotificationService(BaseNotificationService):
    """Implement the notification service for the Ecobee thermostat."""

    def __init__(self, ecobee: Ecobee) -> None:
        """Initialize the service."""
        self.ecobee = ecobee

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message."""
        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            raise ValueError("Missing required argument: target")

        for target in targets:
            thermostat_index = int(target)
            self.ecobee.send_message(thermostat_index, message)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat."""

    data: EcobeeData = hass.data[DOMAIN]
    entities = []

    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        entities.append(EcobeeNotifyEntity(data, index, thermostat))

    async_add_entities(entities, True)


class EcobeeNotifyEntity(NotifyEntity):
    """Implement the notification entity for the Ecobee thermostat."""

    _attr_name = None
    _attr_has_entity_name = True

    def __init__(
        self, data: EcobeeData, thermostat_index: int, thermostat: dict
    ) -> None:
        """Initialize the thermostat."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = thermostat
        self._attr_unique_id = self.thermostat["identifier"]
        self.update_without_throttle = False
        model: str | None = None
        with suppress(KeyError):
            model = f"{ECOBEE_MODEL_TO_NAME[self.thermostat['modelNumber']]} Thermostat"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=model,
            name=self.thermostat["name"],
        )

    def send_message(self, message: str) -> None:
        """Send a message."""
        self.data.ecobee.send_message(self.thermostat_index, message)
