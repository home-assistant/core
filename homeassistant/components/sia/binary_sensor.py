"""Module for SIA Binary Sensors."""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from pysiaalarm import SIAEvent

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ZONES,
    SIA_HUB_ZONE,
    SIA_UNIQUE_ID_FORMAT_BINARY,
    SIA_UNIQUE_ID_FORMAT_HUB,
)
from .sia_entity_base import SIABaseEntity

_LOGGER = logging.getLogger(__name__)

CODE_CONSEQUENCES: dict[str, dict[str, bool]] = {
    DEVICE_CLASS_SMOKE: {
        "GA": True,
        "GH": False,
        "FA": True,
        "FH": False,
        "KA": True,
        "KH": False,
    },
    DEVICE_CLASS_MOISTURE: {
        "WA": True,
        "WH": False,
    },
    DEVICE_CLASS_POWER: {
        "AT": False,
        "AR": True,
    },
}

CONNECTIVITY_CODE = "RP"

CONNECTED_ICON = "mdi:lan-connect"
DISCONNECTED_ICON = "mdi:lan-disconnect"


def generate_binary_sensors(entry) -> Iterable[SIABinarySensorBase]:
    """Generate binary sensors.

    For each Account there is one power and one connectivity sensor with zone == 0.
    For each Zone in each Account there is one smoke and one moisture sensor.
    """
    for account in entry.data[CONF_ACCOUNTS]:
        yield SIABinarySensorConnectivity(entry, account)
        yield SIABinarySensorRegular(
            entry,
            account,
            SIA_HUB_ZONE,
            True,
            DEVICE_CLASS_POWER,
        )
        zones = entry.options[CONF_ACCOUNTS][account[CONF_ACCOUNT]][CONF_ZONES]
        for zone in range(1, zones + 1):
            yield SIABinarySensorRegular(
                entry, account, zone, False, DEVICE_CLASS_SMOKE
            )
            yield SIABinarySensorRegular(
                entry,
                account,
                zone,
                False,
                DEVICE_CLASS_MOISTURE,
            )


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
        zone: int | None,
        device_class: str,
        enabled: bool,
    ) -> None:
        """Initialize a base binary sensor."""
        super().__init__(entry, account_data, zone, device_class)
        self._attr_entity_registry_enabled_default = enabled
        if self._zone is None:
            self._attr_unique_id = SIA_UNIQUE_ID_FORMAT_HUB.format(
                self._entry.entry_id, self._account, self._attr_device_class
            )
        else:
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


class SIABinarySensorRegular(SIABinarySensorBase):
    """Class for Smoke, Moisture, and Power Binary Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
        zone: int,
        enabled: bool,
        device_class: str,
    ) -> None:
        """Initialize a binary sensor."""
        super().__init__(entry, account_data, zone, device_class, enabled)
        self.consequences = CODE_CONSEQUENCES[device_class]

    def update_state(self, sia_event: SIAEvent) -> None:
        """Update the state of the binary sensor."""
        new_state = self.consequences.get(sia_event.code, None)
        if new_state is not None:
            _LOGGER.debug("New state will be %s", new_state)
            self._attr_is_on = new_state


class SIABinarySensorConnectivity(SIABinarySensorBase):
    """Class for Connectivity Binary Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
    ) -> None:
        """Initialize a Connectivity binary sensor."""
        super().__init__(entry, account_data, None, DEVICE_CLASS_CONNECTIVITY, True)
        self._attr_icon = CONNECTED_ICON if self._attr_is_on else DISCONNECTED_ICON

    def update_state(self, sia_event: SIAEvent) -> None:
        """Update the state of the binary sensor."""
        if sia_event.code == CONNECTIVITY_CODE:
            self._attr_is_on = True
            self._attr_icon = CONNECTED_ICON

    @callback
    def async_set_unavailable(self, _) -> None:
        """Overwrite set unavailable from entity base."""
        self._attr_is_on = False
        self._attr_icon = DISCONNECTED_ICON
        self.async_write_ha_state()
