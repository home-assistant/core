"""Support for Honeywell (US) Total Connect Comfort climate systems."""

import somecomfort
import logging
from datetime import timedelta

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryNotReady


_LOGGER = logging.getLogger(__name__)
client_key_coordinator = "client_key_coordinator"


import asyncio
from functools import wraps, partial


# base class to be used by honeywell thermostat sensors and thermostats
class HoneywellDevice(CoordinatorEntity):
    def __init__(self, coordinator, device):
        # the coordinator updates the device object
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device


# decorator that allows IO functions to run in a background thread
# so they can be called in async functions
def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


@async_wrap
def some_comfort_refresh_async_wrap(device):
    device.refresh()


@async_wrap
def create_client_wrap_async(username, password):
    return somecomfort.SomeComfort(username, password)


async def login_to_honeywell(username, password):
    try:
        client = await create_client_wrap_async(username, password)
    except somecomfort.AuthError as e:
        _LOGGER.error("Failed to login to honeywell account %s", username)
        raise e
    except somecomfort.SomeComfortError:
        _LOGGER.error(
            "Failed to initialize the Honeywell client: "
            "Check your configuration (username, password), "
            "or maybe you have exceeded the API rate limit?"
        )
        raise e

    return client


async def async_setup(hass, config):

    # get the username and password from the climate integration
    # it is required to be present in the climate schema
    climates = config["climate"]
    for climate_config in climates:
        if climate_config["platform"] == "honeywell":
            username = climate_config[CONF_USERNAME]
            password = climate_config[CONF_PASSWORD]

    client = None
    try:
        client = await login_to_honeywell(username, password)
    except somecomfort.client.APIRateLimited as e:
        _LOGGER.error(
            "Failed to login to honeywell account during setup due to rate limit."
        )
        _LOGGER.error(" Will retry in async_setup_platform")

    async def async_update_data():
        # Fetch data from API endpoint.
        _LOGGER.info("attempting to update honeywell data")

        # if the login didn't work during async_setup due to rate limiting, try again here
        nonlocal client
        if client is None:
            try:
                client = await login_to_honeywell(username, password)
            except somecomfort.client.APIRateLimited as e:
                _LOGGER.error(
                    "Failed to login to honeywell account during async_update_data due to rate limit."
                )
                _Logger.error(" Will retry later")

        # assuming we got a working login, try getting the data
        try:
            # we have to make a different request for each device
            for location in client.locations_by_id.values():
                for device in location.devices_by_id.values():
                    await some_comfort_refresh_async_wrap(device)
                    _LOGGER.debug(
                        "latestData = %s ",
                        device._data,  # pylint: disable=protected-access
                    )
        except (
            somecomfort.client.APIRateLimited,
            OSError,
            requests.exceptions.ReadTimeout,
        ) as exp:
            _LOGGER.error("SomeComfort update failed - Error: %s", exp)
            raise UpdateFailed(str(exp))

        return client

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="honeywell_update_coordinator",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=300),
    )

    hass.data[client_key_coordinator] = coordinator

    return True
