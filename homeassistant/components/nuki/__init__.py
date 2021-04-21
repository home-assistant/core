"""The nuki component."""

import asyncio
from datetime import timedelta
import logging

import async_timeout
from pynuki import NukiBridge
from pynuki.bridge import InvalidCredentialsException
from requests.exceptions import RequestException

from homeassistant import exceptions
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DATA_BRIDGE,
    DATA_COORDINATOR,
    DATA_LOCKS,
    DATA_OPENERS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ERROR_STATES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "lock"]
UPDATE_INTERVAL = timedelta(seconds=30)


def _get_bridge_devices(bridge):
    return bridge.locks, bridge.openers


def _update_devices(devices):
    for device in devices:
        for level in (False, True):
            try:
                device.update(level)
            except RequestException:
                continue

            if device.state not in ERROR_STATES:
                break


async def async_setup(hass, config):
    """Set up the Nuki component."""
    hass.data.setdefault(DOMAIN, {})

    for platform in PLATFORMS:
        confs = config.get(platform)
        if confs is None:
            continue

        for conf in confs:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up the Nuki entry."""

    hass.data.setdefault(DOMAIN, {})

    try:
        bridge = await hass.async_add_executor_job(
            NukiBridge,
            entry.data[CONF_HOST],
            entry.data[CONF_TOKEN],
            entry.data[CONF_PORT],
            True,
            DEFAULT_TIMEOUT,
        )

        locks, openers = await hass.async_add_executor_job(_get_bridge_devices, bridge)
    except InvalidCredentialsException as err:
        raise exceptions.ConfigEntryAuthFailed from err
    except RequestException as err:
        raise exceptions.ConfigEntryNotReady from err

    async def async_update_data():
        """Fetch data from Nuki bridge."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                await hass.async_add_executor_job(_update_devices, locks + openers)
        except InvalidCredentialsException as err:
            raise UpdateFailed(f"Invalid credentials for Bridge: {err}") from err
        except RequestException as err:
            raise UpdateFailed(f"Error communicating with Bridge: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="nuki devices",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=UPDATE_INTERVAL,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_BRIDGE: bridge,
        DATA_LOCKS: locks,
        DATA_OPENERS: openers,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload the Nuki entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NukiEntity(CoordinatorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator, nuki_device):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._nuki_device = nuki_device
