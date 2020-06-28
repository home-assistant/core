"""Switches for the Elexa Guardian integration."""
from aioguardian.commands.system import (
    DEFAULT_FIRMWARE_UPGRADE_FILENAME,
    DEFAULT_FIRMWARE_UPGRADE_PORT,
    DEFAULT_FIRMWARE_UPGRADE_URL,
)
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_FILENAME, CONF_PORT, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.service import verify_domain_control

from . import Guardian, GuardianEntity
from .const import DATA_CLIENT, DATA_VALVE_STATUS, DOMAIN, LOGGER, SWITCH_KIND_VALVE

ATTR_AVG_CURRENT = "average_current"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_TRAVEL_COUNT = "travel_count"

SERVICE_UPGRADE_FIRMWARE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_URL, default=DEFAULT_FIRMWARE_UPGRADE_URL): cv.url,
        vol.Optional(CONF_PORT, default=DEFAULT_FIRMWARE_UPGRADE_PORT): cv.port,
        vol.Optional(
            CONF_FILENAME, default=DEFAULT_FIRMWARE_UPGRADE_FILENAME
        ): cv.string,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Guardian switches based on a config entry."""
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    guardian = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    @_verify_domain_control
    async def disable_ap(call):
        """Disable the device's onboard access point."""
        try:
            async with guardian.client:
                await guardian.client.wifi.disable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def enable_ap(call):
        """Enable the device's onboard access point."""
        try:
            async with guardian.client:
                await guardian.client.wifi.enable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def reboot(call):
        """Reboot the device."""
        try:
            async with guardian.client:
                await guardian.client.system.reboot()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def reset_valve_diagnostics(call):
        """Fully reset system motor diagnostics."""
        try:
            async with guardian.client:
                await guardian.client.valve.reset()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @_verify_domain_control
    async def upgrade_firmware(call):
        """Upgrade the device firmware."""
        try:
            async with guardian.client:
                await guardian.client.system.upgrade_firmware(
                    url=call.data[CONF_URL],
                    port=call.data[CONF_PORT],
                    filename=call.data[CONF_FILENAME],
                )
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    platform = entity_platform.current_platform.get()

    for service, method, schema in [
        ("disable_ap", disable_ap, None),
        ("enable_ap", enable_ap, None),
        ("reboot", reboot, None),
        ("reset_valve_diagnostics", reset_valve_diagnostics, None),
        ("upgrade_firmware", upgrade_firmware, SERVICE_UPGRADE_FIRMWARE_SCHEMA),
    ]:
        platform.async_register_entity_service(service, schema, method)

    async_add_entities([GuardianSwitch(guardian)], True)


class GuardianSwitch(GuardianEntity, SwitchEntity):
    """Define a switch to open/close the Guardian valve."""

    def __init__(self, guardian: Guardian):
        """Initialize."""
        super().__init__(guardian, SWITCH_KIND_VALVE, "Valve", None, "mdi:water")

        self._is_on = True

    @property
    def is_on(self):
        """Return True if the valve is open."""
        return self._is_on

    @callback
    def _update_from_latest_data(self):
        """Update the entity."""
        self._is_on = self._guardian.data[DATA_VALVE_STATUS]["state"] in (
            "start_opening",
            "opening",
            "finish_opening",
            "opened",
        )

        self._attrs.update(
            {
                ATTR_AVG_CURRENT: self._guardian.data[DATA_VALVE_STATUS][
                    "average_current"
                ],
                ATTR_INST_CURRENT: self._guardian.data[DATA_VALVE_STATUS][
                    "instantaneous_current"
                ],
                ATTR_INST_CURRENT_DDT: self._guardian.data[DATA_VALVE_STATUS][
                    "instantaneous_current_ddt"
                ],
                ATTR_TRAVEL_COUNT: self._guardian.data[DATA_VALVE_STATUS][
                    "travel_count"
                ],
            }
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the valve off (closed)."""
        try:
            async with self._guardian.client:
                await self._guardian.client.valve.close()
        except GuardianError as err:
            LOGGER.error("Error while closing the valve: %s", err)
            return

        self._is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the valve on (open)."""
        try:
            async with self._guardian.client:
                await self._guardian.client.valve.open()
        except GuardianError as err:
            LOGGER.error("Error while opening the valve: %s", err)
            return

        self._is_on = True
        self.async_write_ha_state()
