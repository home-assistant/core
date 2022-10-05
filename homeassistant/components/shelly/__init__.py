"""The Shelly integration."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import Any, Final, cast

from aiohttp import ClientResponseError
import aioshelly
from aioshelly.block_device import BlockDevice
from aioshelly.exceptions import AuthRequired, InvalidAuthError
from aioshelly.rpc_device import RpcDevice
import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    BLOCK,
    CONF_COAP_PORT,
    CONF_SLEEP_PERIOD,
    DATA_CONFIG_ENTRY,
    DEFAULT_COAP_PORT,
    DEVICE,
    DOMAIN,
    LOGGER,
    REST,
    RPC,
    RPC_POLL,
)
from .coordinator import (
    ShellyBlockCoordinator,
    ShellyRestCoordinator,
    ShellyRpcCoordinator,
    ShellyRpcPollingCoordinator,
)
from .utils import get_block_device_sleep_period, get_coap_context, get_device_entry_gen

BLOCK_PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]
BLOCK_SLEEPING_PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]
RPC_PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


COAP_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_COAP_PORT, default=DEFAULT_COAP_PORT): cv.port,
    }
)
CONFIG_SCHEMA: Final = vol.Schema({DOMAIN: COAP_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Shelly component."""
    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}

    if (conf := config.get(DOMAIN)) is not None:
        hass.data[DOMAIN][CONF_COAP_PORT] = conf[CONF_COAP_PORT]

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly from a config entry."""
    # The custom component for Shelly devices uses shelly domain as well as core
    # integration. If the user removes the custom component but doesn't remove the
    # config entry, core integration will try to configure that config entry with an
    # error. The config entry data for this custom component doesn't contain host
    # value, so if host isn't present, config entry will not be configured.
    if not entry.data.get(CONF_HOST):
        LOGGER.warning(
            "The config entry %s probably comes from a custom integration, please remove it if you want to use core Shelly integration",
            entry.title,
        )
        return False

    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = {}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = None

    if get_device_entry_gen(entry) == 2:
        return await async_setup_rpc_entry(hass, entry)

    return await async_setup_block_entry(hass, entry)


async def async_setup_block_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly block based device from a config entry."""
    temperature_unit = "C" if hass.config.units.is_metric else "F"

    options = aioshelly.common.ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        temperature_unit,
    )

    coap_context = await get_coap_context(hass)

    device = await BlockDevice.create(
        aiohttp_client.async_get_clientsession(hass),
        coap_context,
        options,
        False,
    )

    dev_reg = device_registry.async_get(hass)
    device_entry = None
    if entry.unique_id is not None:
        device_entry = dev_reg.async_get_device(
            identifiers=set(),
            connections={
                (
                    device_registry.CONNECTION_NETWORK_MAC,
                    device_registry.format_mac(entry.unique_id),
                )
            },
        )
    if device_entry and entry.entry_id not in device_entry.config_entries:
        device_entry = None

    sleep_period = entry.data.get(CONF_SLEEP_PERIOD)

    @callback
    def _async_device_online(_: Any) -> None:
        LOGGER.debug("Device %s is online, resuming setup", entry.title)
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = None

        if sleep_period is None:
            data = {**entry.data}
            data[CONF_SLEEP_PERIOD] = get_block_device_sleep_period(device.settings)
            data["model"] = device.settings["device"]["type"]
            hass.config_entries.async_update_entry(entry, data=data)

        async_block_device_setup(hass, entry, device)

    if sleep_period == 0:
        # Not a sleeping device, finish setup
        LOGGER.debug("Setting up online block device %s", entry.title)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                await device.initialize()
                await device.update_status()
        except asyncio.TimeoutError as err:
            raise ConfigEntryNotReady(
                str(err) or "Timeout during device setup"
            ) from err
        except OSError as err:
            raise ConfigEntryNotReady(str(err) or "Error during device setup") from err
        except AuthRequired as err:
            raise ConfigEntryAuthFailed from err
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise ConfigEntryAuthFailed from err

        async_block_device_setup(hass, entry, device)
    elif sleep_period is None or device_entry is None:
        # Need to get sleep info or first time sleeping device setup, wait for device
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][DEVICE] = device
        LOGGER.debug(
            "Setup for device %s will resume when device is online", entry.title
        )
        device.subscribe_updates(_async_device_online)
    else:
        # Restore sensors for sleeping device
        LOGGER.debug("Setting up offline block device %s", entry.title)
        async_block_device_setup(hass, entry, device)

    return True


@callback
def async_block_device_setup(
    hass: HomeAssistant, entry: ConfigEntry, device: BlockDevice
) -> None:
    """Set up a block based device that is online."""
    block_coordinator = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        BLOCK
    ] = ShellyBlockCoordinator(hass, entry, device)
    block_coordinator.async_setup()

    platforms = BLOCK_SLEEPING_PLATFORMS

    if not entry.data.get(CONF_SLEEP_PERIOD):
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
            REST
        ] = ShellyRestCoordinator(hass, device, entry)
        platforms = BLOCK_PLATFORMS

    hass.config_entries.async_setup_platforms(entry, platforms)


async def async_setup_rpc_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly RPC based device from a config entry."""
    options = aioshelly.common.ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )

    LOGGER.debug("Setting up online RPC device %s", entry.title)
    try:
        async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
            device = await RpcDevice.create(
                aiohttp_client.async_get_clientsession(hass), options
            )
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(str(err) or "Timeout during device setup") from err
    except OSError as err:
        raise ConfigEntryNotReady(str(err) or "Error during device setup") from err
    except (AuthRequired, InvalidAuthError) as err:
        raise ConfigEntryAuthFailed from err

    rpc_coordinator = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        RPC
    ] = ShellyRpcCoordinator(hass, entry, device)
    rpc_coordinator.async_setup()

    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][
        RPC_POLL
    ] = ShellyRpcPollingCoordinator(hass, entry, device)

    hass.config_entries.async_setup_platforms(entry, RPC_PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if get_device_entry_gen(entry) == 2:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, RPC_PLATFORMS
        )
        if unload_ok:
            await hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][RPC].shutdown()
            hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)

        return unload_ok

    device = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id].get(DEVICE)
    if device is not None:
        # If device is present, block coordinator is not setup yet
        device.shutdown()
        return True

    platforms = BLOCK_SLEEPING_PLATFORMS

    if not entry.data.get(CONF_SLEEP_PERIOD):
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][REST] = None
        platforms = BLOCK_PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id][BLOCK].shutdown()
        hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)

    return unload_ok


def get_block_device_coordinator(
    hass: HomeAssistant, device_id: str
) -> ShellyBlockCoordinator | None:
    """Get a Shelly block device coordinator for the given device id."""
    if not hass.data.get(DOMAIN):
        return None

    dev_reg = device_registry.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for config_entry in device.config_entries:
            if not hass.data[DOMAIN][DATA_CONFIG_ENTRY].get(config_entry):
                continue

            if coordinator := hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry].get(
                BLOCK
            ):
                return cast(ShellyBlockCoordinator, coordinator)

    return None


def get_rpc_device_coordinator(
    hass: HomeAssistant, device_id: str
) -> ShellyRpcCoordinator | None:
    """Get a Shelly RPC device coordinator for the given device id."""
    if not hass.data.get(DOMAIN):
        return None

    dev_reg = device_registry.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for config_entry in device.config_entries:
            if not hass.data[DOMAIN][DATA_CONFIG_ENTRY].get(config_entry):
                continue

            if coordinator := hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry].get(
                RPC
            ):
                return cast(ShellyRpcCoordinator, coordinator)

    return None
