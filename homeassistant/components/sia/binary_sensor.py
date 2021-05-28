"""Module for SIA Alarm Control Panels."""
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
from .utils import get_attr_from_sia_event

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

ZONE_DEVICES = [
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_SMOKE,
]


def generate_binary_sensors(entry) -> Iterable[SIABinarySensor]:
    """Generate binary sensors.

    For each Account there is one power sensor with zone == 0.
    For each Zone in each Account there is one smoke and one moisture sensor.
    """
    for account in entry.data[CONF_ACCOUNTS]:
        yield SIABinarySensor(entry, account, SIA_HUB_ZONE, DEVICE_CLASS_POWER)
        zones = entry.options[CONF_ACCOUNTS][account[CONF_ACCOUNT]][CONF_ZONES]
        for zone in range(1, zones + 1):
            for device_class in ZONE_DEVICES:
                yield SIABinarySensor(entry, account, zone, device_class)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SIA binary sensors from a config entry."""
    async_add_entities(generate_binary_sensors(entry))


class SIABinarySensor(BinarySensorEntity, SIABaseEntity):
    """Class for SIA Binary Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
        zone: int,
        device_class: str,
    ) -> None:
        """Create SIABinarySensor object."""
        super().__init__(entry, account_data, zone, device_class)
        self._is_on: bool | None = None

    def update_state_and_attr(self, sia_event: SIAEvent) -> None:
        """Update the state of the binary sensor."""
        if int(sia_event.ri) == self._zone:
            self._attr.update(get_attr_from_sia_event(sia_event))
            new_state = None
            if self._device_class == DEVICE_CLASS_POWER:
                new_state = POWER_CODE_CONSEQUENCES.get(sia_event.code, None)
            elif self._device_class == DEVICE_CLASS_MOISTURE:
                new_state = MOISTURE_CODE_CONSEQUENCES.get(sia_event.code, None)
            elif self._device_class == DEVICE_CLASS_SMOKE:
                new_state = SMOKE_CODE_CONSEQUENCES.get(sia_event.code, None)
            if new_state is not None:
                _LOGGER.debug("New state will be %s", new_state)
                self._is_on = new_state

    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""
        if last_state is not None and last_state.state is not None:
            if last_state.state == STATE_ON:
                self._is_on = True
            elif last_state.state == STATE_OFF:
                self._is_on = False
            elif last_state.state == STATE_UNAVAILABLE:
                self._is_on = None
                self._available = False

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def unique_id(self) -> str:
        """Get unique_id."""
        return SIA_UNIQUE_ID_FORMAT_BINARY.format(
            self._entry.entry_id, self._account, self._zone, self._device_class
        )
