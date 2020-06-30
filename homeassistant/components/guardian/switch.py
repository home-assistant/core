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

from . import Guardian, GuardianEntity
from .const import DATA_CLIENT, DATA_VALVE_STATUS, DOMAIN, LOGGER, SWITCH_KIND_VALVE

ATTR_AVG_CURRENT = "average_current"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_TRAVEL_COUNT = "travel_count"

SERVICE_DISABLE_AP = "disable_ap"
SERVICE_ENABLE_AP = "enable_ap"
SERVICE_REBOOT = "reboot"
SERVICE_RESET_VALVE_DIAGNOSTICS = "reset_valve_diagnostics"
SERVICE_UPGRADE_FIRMWARE = "upgrade_firmware"

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
    guardian = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    platform = entity_platform.current_platform.get()

    for service_name, schema, method in [
        (SERVICE_DISABLE_AP, None, "async_disable_ap"),
        (SERVICE_ENABLE_AP, None, "async_enable_ap"),
        (SERVICE_REBOOT, None, "async_reboot"),
        (SERVICE_RESET_VALVE_DIAGNOSTICS, None, "async_reset_valve_diagnostics"),
        (
            SERVICE_UPGRADE_FIRMWARE,
            SERVICE_UPGRADE_FIRMWARE_SCHEMA,
            "async_upgrade_firmware",
        ),
    ]:
        platform.async_register_entity_service(service_name, schema, method)

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

    async def async_disable_ap(self):
        """Disable the device's onboard access point."""
        try:
            async with self._guardian.client:
                await self._guardian.client.wifi.disable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_enable_ap(self):
        """Enable the device's onboard access point."""
        try:
            async with self._guardian.client:
                await self._guardian.client.wifi.enable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_reboot(self):
        """Reboot the device."""
        try:
            async with self._guardian.client:
                await self._guardian.client.system.reboot()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_reset_valve_diagnostics(self):
        """Fully reset system motor diagnostics."""
        try:
            async with self._guardian.client:
                await self._guardian.client.valve.reset()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_upgrade_firmware(self, *, url, port, filename):
        """Upgrade the device firmware."""
        try:
            async with self._guardian.client:
                await self._guardian.client.system.upgrade_firmware(
                    url=url, port=port, filename=filename,
                )
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

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
