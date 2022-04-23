"""The sms component."""
from datetime import timedelta
import logging

import async_timeout
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    GATEWAY,
    NETWORK_COORDINATOR,
    SIGNAL_COORDINATOR,
    SMS_GATEWAY,
)
from .gateway import create_sms_gateway

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.isdevice})},
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Configure Gammu state machine."""
    hass.data.setdefault(DOMAIN, {})
    if not (sms_config := config.get(DOMAIN, {})):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=sms_config,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure Gammu state machine."""

    device = entry.data[CONF_DEVICE]
    config = {"Device": device, "Connection": "at"}
    gateway = await create_sms_gateway(config, hass)
    if not gateway:
        return False

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    signal_coordinator = GammuSignalCoordinator(hass, gateway, scan_interval)
    network_coordinator = GammuNetworkCoordinator(hass, gateway, scan_interval)

    # Fetch initial data so we have data when entities subscribe
    await signal_coordinator.async_config_entry_first_refresh()
    await network_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][SMS_GATEWAY] = {
        SIGNAL_COORDINATOR: signal_coordinator,
        NETWORK_COORDINATOR: network_coordinator,
        GATEWAY: gateway,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        gateway = hass.data[DOMAIN].pop(SMS_GATEWAY)[GATEWAY]
        await gateway.terminate_async()

    return unload_ok


class GammuSignalCoordinator(DataUpdateCoordinator):
    """Signal strength coordinator."""

    def __init__(self, hass, gateway, scan_interval):
        """Initialize signal strength coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Gammu signal state",
            update_interval=timedelta(seconds=scan_interval),
        )
        self._gateway = gateway

    async def _async_update_data(self):
        async with async_timeout.timeout(10):
            return await self._gateway.get_signal_quality_async()


class GammuNetworkCoordinator(DataUpdateCoordinator):
    """Network info coordinator."""

    def __init__(self, hass, gateway, scan_interval):
        """Initialize network info coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Gammu network state",
            update_interval=timedelta(seconds=scan_interval),
        )
        self._gateway = gateway

    async def _async_update_data(self):
        async with async_timeout.timeout(10):
            return await self._gateway.get_network_info_async()
