"""Support for Lutron Caseta switches."""

from typing import Any

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import LutronCasetaEntity, LutronCasetaUpdatableEntity
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta switch platform.

    Adds switches from the Caseta bridge associated with the config_entry as
    switch entities.
    """
    data = config_entry.runtime_data
    bridge = data.bridge
    switch_devices = bridge.get_devices_by_domain(SWITCH_DOMAIN)
    entities: list[LutronCasetaLight | LutronCasetaSmartAwaySwitch] = [
        LutronCasetaLight(switch_device, data) for switch_device in switch_devices
    ]

    if bridge.smart_away_state != "":
        entities.append(LutronCasetaSmartAwaySwitch(data))

    async_add_entities(entities)


class LutronCasetaLight(LutronCasetaUpdatableEntity, SwitchEntity):
    """Representation of a Lutron Caseta switch."""

    def __init__(self, device, data):
        """Init a button entity."""

        super().__init__(device, data)
        self._enabled_default = True

        if "parent_device" not in device:
            return

        keypads = data.keypad_data.keypads
        parent_keypad = keypads[device["parent_device"]]
        parent_device_info = parent_keypad["device_info"]
        # Append the child device name to the end of the parent keypad name to create the entity name
        self._attr_name = f"{parent_device_info['name']} {device['device_name']}"
        # Set the device_info to the same as the Parent Keypad
        # The entities will be nested inside the keypad device
        self._attr_device_info = parent_device_info

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._smartbridge.turn_on(self.device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._smartbridge.turn_off(self.device_id)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device["current_state"] > 0


class LutronCasetaSmartAwaySwitch(LutronCasetaEntity, SwitchEntity):
    """Representation of Lutron Caseta Smart Away."""

    def __init__(self, data: LutronCasetaData) -> None:
        """Init a switch entity."""
        device = {
            "device_id": "smart_away",
            "name": "Smart Away",
            "type": "SmartAway",
            "model": "Smart Away",
            "area": data.bridge_device["area"],
            "serial": data.bridge_device["serial"],
        }
        super().__init__(device, data)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.bridge_device["serial"])},
        )
        self._smart_away_unique_id = f"{self._bridge_unique_id}_smart_away"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the smart away switch."""
        return self._smart_away_unique_id

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self._smartbridge.add_smart_away_subscriber(self._handle_smart_away_update)

    def _handle_smart_away_update(self, smart_away_state: str | None = None) -> None:
        """Handle updated smart away state from the bridge."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn Smart Away on."""
        await self._smartbridge.activate_smart_away()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn Smart Away off."""
        await self._smartbridge.deactivate_smart_away()

    @property
    def is_on(self) -> bool:
        """Return true if Smart Away is on."""
        return self._smartbridge.smart_away_state == "Enabled"
