"""Support for Vera locks."""
from __future__ import annotations

import logging

from typing import Any

import voluptuous as vol

from .pyvera import pyvera as veraApi

from homeassistant.components.lock import (
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
    LockEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED, ATTR_CREDENTIALS, HTTP_OK, CONF_COMMAND_STATE, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform
)

from . import VeraDevice
from .common import ControllerData, get_controller_data

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_USER_NAME = "changed_by_name"
ATTR_LOW_BATTERY = "low_battery"
SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
        vol.Required(CONF_PIN): vol.All(int, vol.Range(min=10000000, max=99999999)),
        vol.Optional("slot"): vol.All(int, vol.Range(min=1, max=244)),
    }
)
CLEAR_PIN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
        vol.Required("slot"):  vol.All(int, vol.Range(min=1, max=244)),
    }
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraLock(device, controller_data)
            for device in controller_data.devices.get(PLATFORM_DOMAIN)
        ],
        True,
    )
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "setpin",
        SET_PIN_SCHEMA,
        "_setpin"
    )
    platform.async_register_entity_service(
        "clearpin",
        CLEAR_PIN_SCHEMA,
        "_clearpin"
    )


class VeraLock(VeraDevice[veraApi.VeraLock], LockEntity):
    """Representation of a Vera lock."""

    def __init__(
        self, vera_device: veraApi.VeraLock, controller_data: ControllerData
    ) -> None:
        """Initialize the Vera device."""
        self._state = None
        self._cmd_status = None
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    def lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self.vera_device.lock()
        self._state = STATE_LOCKED

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self.vera_device.unlock()
        self._state = STATE_UNLOCKED
    
    def _setpin(self, **kwargs: Any) -> None:
        """Set pin on the device."""
        _LOGGER.warning("calling veralock.setpin to add %s with pin %s", kwargs[CONF_NAME], kwargs[CONF_PIN])
        result = self.vera_device.set_new_pin(name = kwargs[CONF_NAME], pin = kwargs[CONF_PIN])
        if result.status_code == HTTP_OK:
            self._cmd_status = "Removed"
        else:
            self._cmd_status = result.text
            _LOGGER.error("Failed to call %s: %s", "veralock.setpin", result.text)
            raise ValueError(result.text)
    
    def _clearpin(self, **kwargs: Any) -> None:
        """Clear pin on the device."""
        _LOGGER.warning("calling veralock.clearpin to clear slot %s", kwargs["slot"])
        result = self.vera_device.clear_slot_pin(slot = kwargs["slot"])
        if result.status_code == HTTP_OK:
            self._cmd_status = "Removed"
        else:
            self._cmd_status = result.text
            _LOGGER.error("Failed to call %s: %s", "veralock.clearpin", result.text)
            raise ValueError(result.text)

    @property
    def is_locked(self) -> bool | None:
        """Return true if device is on."""
        return self._state == STATE_LOCKED

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Who unlocked the lock and did a low battery alert fire.

        Reports on the previous poll cycle.
        changed_by_name is a string like 'Bob'.
        low_battery is 1 if an alert fired, 0 otherwise.
        """
        data = super().extra_state_attributes

        last_user = self.vera_device.get_last_user_alert()
        if last_user is not None:
            data[ATTR_LAST_USER_NAME] = last_user[1]

        data[ATTR_LOW_BATTERY] = self.vera_device.get_low_battery_alert()
        data[ATTR_CREDENTIALS] = "{}".format(self.vera_device.get_pin_codes())
        data[CONF_COMMAND_STATE] = self._cmd_status
        return data

    @property
    def changed_by(self) -> str | None:
        """Who unlocked the lock.

        Reports on the previous poll cycle.
        changed_by is an integer user ID.
        """
        last_user = self.vera_device.get_last_user_alert()
        if last_user is not None:
            return last_user[0]
        return None

    def update(self) -> None:
        """Update state by the Vera device callback."""
        self._state = (
            STATE_LOCKED if self.vera_device.is_locked(True) else STATE_UNLOCKED
        )
