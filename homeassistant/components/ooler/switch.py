"""Support for Ooler Sleep System switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import _LOGGER, DOMAIN
from .models import OolerData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ooler switches."""
    data: OolerData = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        OolerCleaningSwitch(data),
        OolerConnectionSwitch(data),
    ]
    async_add_entities(entities)


class OolerCleaningSwitch(SwitchEntity):
    """Representation of Ooler Cleaning switch."""

    _attr_has_entity_name = True

    def __init__(self, data: OolerData) -> None:
        """Initialize the switch entity."""
        self._data = data
        self._attr_name = "Cleaning"
        self._attr_unique_id = f"{data.address}_cleaning_binary_sensor"
        self._attr_device_info = DeviceInfo(
            name=data.model, connections={(dr.CONNECTION_BLUETOOTH, data.address)}
        )

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return self._data.client.is_connected

    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Determine state on start up and register callback."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._data.client.register_callback(self._handle_state_update)
        )

    @property
    def name(self) -> str | None:
        """Return entity name."""
        return self._attr_name

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is cleaning."""
        return self._data.client.state.clean

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start cleaning the unit."""
        client = self._data.client
        if not client.is_connected:
            _LOGGER.debug("Client not connected. Attempting to connect")
            await client.connect()
        await client.set_clean(True)
        _LOGGER.info("Cleaning the device: %s", self.name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Start cleaning the unit."""
        client = self._data.client
        if not client.is_connected:
            _LOGGER.debug("Client not connected. Attempting to connect")
            await client.connect()
        await client.set_clean(False)
        _LOGGER.info("Stopping cleaning process: %s", self.name)


class OolerConnectionSwitch(SwitchEntity):
    """Representation of Ooler bluetooth connection switch."""

    _attr_has_entity_name = True

    def __init__(self, data: OolerData) -> None:
        """Initialize the switch entity."""
        self._data = data
        self._attr_name = "Bluetooth Connection"
        self._attr_unique_id = f"{data.address}_connection_binary_sensor"
        self._attr_device_info = DeviceInfo(
            name=data.model, connections={(dr.CONNECTION_BLUETOOTH, data.address)}
        )

    @property
    def available(self) -> bool:
        """This switch controls availability, so always return true."""
        return True

    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Determine state on start up and register callback."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._data.client.register_callback(self._handle_state_update)
        )

    @property
    def name(self) -> str | None:
        """Return entity name."""
        return self._attr_name

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is connected."""
        return self._data.client.state.connected

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Connect to the device."""
        client = self._data.client
        if not client.is_connected:
            _LOGGER.debug("Client not connected. Attempting to connect")
            await client.connect()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disconnect from the device."""
        client = self._data.client
        if client.is_connected:
            _LOGGER.debug("Client is connected. Attempting to disconnect")
            await client.stop()
