"""MyAir climate integration."""

import asyncio
import collections.abc
from datetime import timedelta
import json
import logging

from aiohttp import ClientError, ClientTimeout, ServerConnectionError, request

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.helpers import collection, device_registry, entity_component
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import *

_LOGGER = logging.getLogger(__name__)


def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


async def async_setup(hass, config):
    """Set up MyAir."""
    hass.data[DOMAIN] = {}
    for platform in ADVANTAGE_AIR_PLATFORMS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(platform, DOMAIN, {}, config)
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up MyAir Config."""
    url = config_entry.data["url"]

    async def async_update_data():
        data = {}
        count = 0
        while count < ADVANTAGE_AIR_RETRY:
            try:
                async with request(
                    "GET", f"{url}/getSystemData", timeout=ClientTimeout(total=4)
                ) as resp:
                    assert resp.status == 200
                    data = await resp.json(content_type=None)
            except ConnectionResetError:
                pass
            except ServerConnectionError:
                pass
            except ClientError as err:
                raise UpdateFailed(f"Client Error {err}")

            if "aircons" in data:
                return data

            count += 1
            _LOGGER.debug(f"Waiting and then retrying, Try: {count}")
            await asyncio.sleep(1)
        raise UpdateFailed(f"Tried {ADVANTAGE_AIR_RETRY} times to get MyAir data")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="MyAir",
        update_method=async_update_data,
        update_interval=timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL),
    )

    ready = True
    queue = {}

    async def async_set_data(change):
        nonlocal ready
        nonlocal queue
        queue = update(queue, change)
        if ready:
            ready = False
            while queue:
                while queue:
                    payload = queue
                    queue = {}
                    # try:
                    async with request(
                        "GET",
                        f"{url}/setAircon",
                        params={"json": json.dumps(payload)},
                        timeout=ClientTimeout(total=4),
                    ) as resp:
                        data = await resp.json(content_type=None)
                    # except ClientError as err:
                    #    raise UpdateFailed(err)

                    if data["ack"] == False:
                        ready = True
                        raise Exception(data["reason"])
                await coordinator.async_refresh()  # Request refresh once queue is empty
            ready = (
                True  # Ready only once refresh has finished and queue is still empty
            )
        return

    # Fetch initial data so we have data when entities subscribe
    while not coordinator.data:
        await coordinator.async_refresh()

    if "system" in coordinator.data:
        device = {
            "identifiers": {(DOMAIN, coordinator.data["system"]["rid"])},
            "name": coordinator.data["system"]["name"],
            "manufacturer": "Advantage Air",
            "model": coordinator.data["system"]["sysType"],
            "sw_version": coordinator.data["system"]["myAppRev"],
        }
    else:
        device = None

    hass.data[DOMAIN][url] = {
        "coordinator": coordinator,
        "async_set_data": async_set_data,
        "device": device,
    }

    # Setup Platforms
    for platform in ADVANTAGE_AIR_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True
