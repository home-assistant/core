"""Switches for the Elexa Guardian integration."""
from typing import Callable, Dict

from aioguardian import Client
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME, CONF_PORT, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import GuardianEntity
from .const import API_VALVE_STATUS, DATA_CLIENT, DATA_COORDINATOR, DOMAIN, LOGGER

ATTR_AVG_CURRENT = "average_current"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_TRAVEL_COUNT = "travel_count"

SERVICE_DISABLE_AP = "disable_ap"
SERVICE_ENABLE_AP = "enable_ap"
SERVICE_REBOOT = "reboot"
SERVICE_RESET_VALVE_DIAGNOSTICS = "reset_valve_diagnostics"
SERVICE_UPGRADE_FIRMWARE = "upgrade_firmware"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Guardian switches based on a config entry."""
    platform = entity_platform.current_platform.get()

    for service_name, schema, method in [
        (SERVICE_DISABLE_AP, {}, "async_disable_ap"),
        (SERVICE_ENABLE_AP, {}, "async_enable_ap"),
        (SERVICE_REBOOT, {}, "async_reboot"),
        (SERVICE_RESET_VALVE_DIAGNOSTICS, {}, "async_reset_valve_diagnostics"),
        (
            SERVICE_UPGRADE_FIRMWARE,
            {
                vol.Optional(CONF_URL): cv.url,
                vol.Optional(CONF_PORT): cv.port,
                vol.Optional(CONF_FILENAME): cv.string,
            },
            "async_upgrade_firmware",
        ),
    ]:
        platform.async_register_entity_service(service_name, schema, method)

    async_add_entities(
        [
            GuardianSwitch(
                entry,
                hass.data[DOMAIN][DATA_CLIENT][entry.entry_id],
                hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id],
            )
        ],
        True,
    )


class GuardianSwitch(GuardianEntity, SwitchEntity):
    """Define a switch to open/close the Guardian valve."""

    def __init__(
        self,
        entry: ConfigEntry,
        client: Client,
        coordinators: Dict[str, DataUpdateCoordinator],
    ):
        """Initialize."""
        super().__init__(
            entry, client, coordinators, "valve", "Valve", None, "mdi:water"
        )

        self._is_on = True

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._coordinators[API_VALVE_STATUS].last_update_success

    @property
    def is_on(self) -> bool:
        """Return True if the valve is open."""
        return self._is_on

    async def _async_internal_added_to_hass(self):
        """Register API interest (and related tasks) when the entity is added."""
        self.async_add_coordinator_update_listener(API_VALVE_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        self._is_on = self._coordinators[API_VALVE_STATUS].data["state"] in (
            "start_opening",
            "opening",
            "finish_opening",
            "opened",
        )

        self._attrs.update(
            {
                ATTR_AVG_CURRENT: self._coordinators[API_VALVE_STATUS].data[
                    "average_current"
                ],
                ATTR_INST_CURRENT: self._coordinators[API_VALVE_STATUS].data[
                    "instantaneous_current"
                ],
                ATTR_INST_CURRENT_DDT: self._coordinators[API_VALVE_STATUS].data[
                    "instantaneous_current_ddt"
                ],
                ATTR_TRAVEL_COUNT: self._coordinators[API_VALVE_STATUS].data[
                    "travel_count"
                ],
            }
        )

    async def async_disable_ap(self):
        """Disable the device's onboard access point."""
        try:
            async with self._client:
                await self._client.wifi.disable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_enable_ap(self):
        """Enable the device's onboard access point."""
        try:
            async with self._client:
                await self._client.wifi.enable_ap()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_reboot(self):
        """Reboot the device."""
        try:
            async with self._client:
                await self._client.system.reboot()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_reset_valve_diagnostics(self):
        """Fully reset system motor diagnostics."""
        try:
            async with self._client:
                await self._client.valve.reset()
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_upgrade_firmware(self, *, url, port, filename):
        """Upgrade the device firmware."""
        try:
            async with self._client:
                await self._client.system.upgrade_firmware(
                    url=url, port=port, filename=filename,
                )
        except GuardianError as err:
            LOGGER.error("Error during service call: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the valve off (closed)."""
        try:
            async with self._client:
                await self._client.valve.close()
        except GuardianError as err:
            LOGGER.error("Error while closing the valve: %s", err)
            return

        self._is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the valve on (open)."""
        try:
            async with self._client:
                await self._client.valve.open()
        except GuardianError as err:
            LOGGER.error("Error while opening the valve: %s", err)
            return

        self._is_on = True
        self.async_write_ha_state()
