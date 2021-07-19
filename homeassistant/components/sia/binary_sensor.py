"""Module for SIA Binary Sensors."""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from pysiaalarm import SIAEvent

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ZONES,
    SIA_HUB_ZONE,
    SIA_UNIQUE_ID_FORMAT_BINARY,
)
from .sia_entity_base import SIABaseEntity

_LOGGER = logging.getLogger(__name__)


POWER_CODE_CONSEQUENCES: dict[str, bool] = {
    "AT": False,
    "AR": True,
}

SMOKE_CODE_CONSEQUENCES: dict[str, bool] = {
    "GA": True,
    "GH": False,
    "FA": True,
    "FH": False,
    "KA": True,
    "KH": False,
}

MOISTURE_CODE_CONSEQUENCES: dict[str, bool] = {
    "WA": True,
    "WH": False,
}


def generate_binary_sensors(entry) -> Iterable[SIABinarySensorBase]:
    """Generate binary sensors.

    For each Account there is one power sensor with zone == 0.
    For each Zone in each Account there is one smoke and one moisture sensor.
    """
    for account in entry.data[CONF_ACCOUNTS]:
        yield SIABinarySensorPower(entry, account)
        zones = entry.options[CONF_ACCOUNTS][account[CONF_ACCOUNT]][CONF_ZONES]
        for zone in range(1, zones + 1):
            yield SIABinarySensorSmoke(entry, account, zone)
            yield SIABinarySensorMoisture(entry, account, zone)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SIA binary sensors from a config entry."""
    async_add_entities(generate_binary_sensors(entry))


class SIABinarySensorBase(SIABaseEntity, BinarySensorEntity):
    """Class for SIA Binary Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
        zone: int,
        device_class: str,
    ) -> None:
        """Initialize a base binary sensor."""
        super().__init__(entry, account_data, zone, device_class)

        self._attr_unique_id = SIA_UNIQUE_ID_FORMAT_BINARY.format(
            self._entry.entry_id, self._account, self._zone, self._attr_device_class
        )

    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""
        if last_state is not None and last_state.state is not None:
            if last_state.state == STATE_ON:
                self._attr_is_on = True
            elif last_state.state == STATE_OFF:
                self._attr_is_on = False
            elif last_state.state == STATE_UNAVAILABLE:
                self._attr_available = False


class SIABinarySensorMoisture(SIABinarySensorBase):
    """Class for Moisture Binary Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
        zone: int,
    ) -> None:
        """Initialize a Moisture binary sensor."""
        super().__init__(entry, account_data, zone, DEVICE_CLASS_MOISTURE)
        self._attr_entity_registry_enabled_default = False

    def update_state(self, sia_event: SIAEvent) -> None:
        """Update the state of the binary sensor."""
        new_state = MOISTURE_CODE_CONSEQUENCES.get(sia_event.code, None)
        if new_state is not None:
            _LOGGER.debug("New state will be %s", new_state)
            self._attr_is_on = new_state


class SIABinarySensorSmoke(SIABinarySensorBase):
    """Class for Smoke Binary Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
        zone: int,
    ) -> None:
        """Initialize a Smoke binary sensor."""
        super().__init__(entry, account_data, zone, DEVICE_CLASS_SMOKE)
        self._attr_entity_registry_enabled_default = False

    def update_state(self, sia_event: SIAEvent) -> None:
        """Update the state of the binary sensor."""
        new_state = SMOKE_CODE_CONSEQUENCES.get(sia_event.code, None)
        if new_state is not None:
            _LOGGER.debug("New state will be %s", new_state)
            self._attr_is_on = new_state


class SIABinarySensorPower(SIABinarySensorBase):
    """Class for Power Binary Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
    ) -> None:
        """Initialize a Power binary sensor."""
        super().__init__(entry, account_data, SIA_HUB_ZONE, DEVICE_CLASS_POWER)
        self._attr_entity_registry_enabled_default = True

    def update_state(self, sia_event: SIAEvent) -> None:
        """Update the state of the binary sensor."""
        new_state = POWER_CODE_CONSEQUENCES.get(sia_event.code, None)
        if new_state is not None:
            _LOGGER.debug("New state will be %s", new_state)
            self._attr_is_on = new_state
