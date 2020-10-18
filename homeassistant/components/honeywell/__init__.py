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

_LOGGER = logging.getLogger(__name__)
client_key_coordinator = "client_key_coordinator"


class SomeComfortWrap():

    def __init__(self, username, password):
        self._username = username
        self._password = password
        
        self._client = somecomfort.SomeComfort(username, password)

        
    def retry(self):
        self._client = somecomfort.SomeComfort(self._username, self._password)



class HoneywellDevice(CoordinatorEntity):

    def __init__(self, coordinator, device):
        # the coordinator updates the device object
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        


async def create_client_wrap_async(username, password):
    return somecomfort.SomeComfort(username, password)



async def async_setup(hass, config):

    # get the username and password from the climate integration
    # it is required to be present in the climate schema
    climates = config["climate"]
    for climate_config in climates:
        if climate_config["platform"] == "honeywell":
            username = climate_config[CONF_USERNAME]
            password = climate_config[CONF_PASSWORD]
    
    try:
        client = await create_client_wrap_async(username, password)
    except somecomfort.AuthError:
        _LOGGER.error("Failed to login to honeywell account %s", username)
        return
    except somecomfort.SomeComfortError:
        _LOGGER.error(
            "Failed to initialize the Honeywell client: "
            "Check your configuration (username, password), "
            "or maybe you have exceeded the API rate limit?"
        )
        return
            
    async def async_update_data():
        """Fetch data from API endpoint."""
        retries = 3
        while retries > 0:
            try:
                for location in client.locations_by_id.values():
                    for device in location.devices_by_id.values():
                        device.refresh()
                        _LOGGER.debug(
                            "latestData = %s ", device._data  # pylint: disable=protected-access
                        )
                break
            except (
                somecomfort.client.APIRateLimited,
                OSError,
                requests.exceptions.ReadTimeout,
            ) as exp:
                retries -= 1
                if retries == 0:
                    raise exp
                if not self._retry():
                    raise exp
                _LOGGER.error("SomeComfort update failed, Retrying - Error: %s", exp)


        
        return client
    
    
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="honeywell_update_coordinator",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=120),
    )
    
    await coordinator.async_refresh()
    
    hass.data[client_key_coordinator] = coordinator
    
    return True
