"""Support for Edimax switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import HomeAssistant, SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EdimaxConfigEntry
from .const import DEFAULT_NAME
from .smartplug_adapter import Info, SmartPlugAdapter


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EdimaxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    adapter = config_entry.runtime_data
    async_add_entities(
        [SmartPlugSwitch(adapter, config_entry.data["name"])],
        True,
    )


class SmartPlugSwitch(SwitchEntity):
    """Representation an Edimax Smart Plug switch."""

    adapter: SmartPlugAdapter

    _name: str = DEFAULT_NAME
    _state: str = "OFF"
    _info: Info
    _mac: str

    def __init__(self, adapter, name) -> None:
        """Initialize the switch."""

        self.adapter = adapter
        self._name = name
        self._state = "ON"
        self._mac = "unknown"

    @property
    def unique_id(self) -> str:
        """Return the device's MAC address."""

        return self._mac

    @property
    def name(self) -> str:
        """Return the name of the Smart Plug, if any."""

        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""

        return self.adapter.state == "ON"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""

        self.adapter.state = "ON"

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""

        self.adapter.state = "OFF"

    def update(self) -> None:
        """Update edimax switch."""

        self.adapter.update()

        if not self._info:
            self._info = self.adapter.info
            self._mac = self._info.serial_number

        self._state = self.adapter.state
