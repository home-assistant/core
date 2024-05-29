"""Support for Ecobee Send Message service."""

from __future__ import annotations

from functools import partial
from typing import Any

from homeassistant.components.notify import (
    ATTR_TARGET,
    BaseNotificationService,
    NotifyEntity,
    migrate_notify_issue,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import Ecobee, EcobeeData
from .const import DOMAIN
from .entity import EcobeeBaseEntity


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

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message and raise issue."""
        migrate_notify_issue(self.hass, DOMAIN, "Ecobee", "2024.11.0")
        await self.hass.async_add_executor_job(
            partial(self.send_message, message, **kwargs)
        )

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
    async_add_entities(
        EcobeeNotifyEntity(data, index) for index in range(len(data.ecobee.thermostats))
    )


class EcobeeNotifyEntity(EcobeeBaseEntity, NotifyEntity):
    """Implement the notification entity for the Ecobee thermostat."""

    _attr_name = None
    _attr_has_entity_name = True

    def __init__(self, data: EcobeeData, thermostat_index: int) -> None:
        """Initialize the thermostat."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = (
            f"{self.thermostat["identifier"]}_notify_{thermostat_index}"
        )

    def send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        self.data.ecobee.send_message(self.thermostat_index, message)
