"""Switch representing the shutoff valve for the Flo by Moen integration."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FloConfigEntry, FloDeviceDataUpdateCoordinator
from .entity import FloEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flo switches from config entry."""
    devices = config_entry.runtime_data.devices

    async_add_entities(
        [FloSwitch(device) for device in devices if device.device_type != "puck_oem"]
    )


class FloSwitch(FloEntity, SwitchEntity):
    """Switch class for the Flo by Moen valve."""

    _attr_translation_key = "shutoff_valve"

    def __init__(self, device: FloDeviceDataUpdateCoordinator) -> None:
        """Initialize the Flo switch."""
        super().__init__("shutoff_valve", device)
        self._attr_is_on = device.last_known_valve_state == "open"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self._device.api_client.device.open_valve(self._device.id)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self._device.api_client.device.close_valve(self._device.id)
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def async_update_state(self) -> None:
        """Retrieve the latest valve state and update the state machine."""
        self._attr_is_on = self._device.last_known_valve_state == "open"
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._device.async_add_listener(self.async_update_state))

    async def async_set_mode_home(self):
        """Set the Flo location to home mode."""
        await self._device.async_set_mode_home()

    async def async_set_mode_away(self):
        """Set the Flo location to away mode."""
        await self._device.async_set_mode_away()

    async def async_set_mode_sleep(self, sleep_minutes, revert_to_mode):
        """Set the Flo location to sleep mode."""
        await self._device.async_set_mode_sleep(sleep_minutes, revert_to_mode)

    async def async_run_health_test(self):
        """Run a Flo device health test."""
        await self._device.async_run_health_test()
