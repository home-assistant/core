"""Switch representing the shutoff valve for the Flo by Moen integration."""

from __future__ import annotations

from typing import Any

from aioflo.location import SLEEP_MINUTE_OPTIONS, SYSTEM_MODE_HOME, SYSTEM_REVERT_MODES
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as FLO_DOMAIN
from .coordinator import FloDeviceDataUpdateCoordinator
from .entity import FloEntity

ATTR_REVERT_TO_MODE = "revert_to_mode"
ATTR_SLEEP_MINUTES = "sleep_minutes"
SERVICE_SET_SLEEP_MODE = "set_sleep_mode"
SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_HOME_MODE = "set_home_mode"
SERVICE_RUN_HEALTH_TEST = "run_health_test"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flo switches from config entry."""
    devices: list[FloDeviceDataUpdateCoordinator] = hass.data[FLO_DOMAIN][
        config_entry.entry_id
    ]["devices"]

    async_add_entities(
        [FloSwitch(device) for device in devices if device.device_type != "puck_oem"]
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_AWAY_MODE, {}, "async_set_mode_away"
    )
    platform.async_register_entity_service(
        SERVICE_SET_HOME_MODE, {}, "async_set_mode_home"
    )
    platform.async_register_entity_service(
        SERVICE_RUN_HEALTH_TEST, {}, "async_run_health_test"
    )
    platform.async_register_entity_service(
        SERVICE_SET_SLEEP_MODE,
        {
            vol.Required(ATTR_SLEEP_MINUTES, default=120): vol.All(
                vol.Coerce(int),
                vol.In(SLEEP_MINUTE_OPTIONS),
            ),
            vol.Required(ATTR_REVERT_TO_MODE, default=SYSTEM_MODE_HOME): vol.In(
                SYSTEM_REVERT_MODES
            ),
        },
        "async_set_mode_sleep",
    )


class FloSwitch(FloEntity, SwitchEntity):
    """Switch class for the Flo by Moen valve."""

    _attr_translation_key = "shutoff_valve"

    def __init__(self, device: FloDeviceDataUpdateCoordinator) -> None:
        """Initialize the Flo switch."""
        super().__init__("shutoff_valve", device)
        self._attr_is_on = device.last_known_valve_state == "open"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self._device.api_client.device.open_valve(self._device.id)
        self._attr_is_on = True
        self.async_write_ha_state()

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
