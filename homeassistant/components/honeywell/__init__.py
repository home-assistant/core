"""Support for Honeywell (US) Total Connect Comfort climate systems."""
from datetime import timedelta

import somecomfort

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import Throttle

from .const import _LOGGER, CONF_DEV_ID, CONF_LOC_ID, DOMAIN

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)
PLATFORMS = ["climate"]


async def async_setup_entry(hass, config):
    """Set up the Honeywell thermostat."""
    username = config.data[CONF_USERNAME]
    password = config.data[CONF_PASSWORD]

    client = await hass.async_add_executor_job(
        get_somecomfort_client, username, password
    )

    if client is None:
        return False

    loc_id = config.data.get(CONF_LOC_ID)
    dev_id = config.data.get(CONF_DEV_ID)

    devices = []

    for location in client.locations_by_id.values():
        for device in location.devices_by_id.values():
            if (not loc_id or location.locationid == loc_id) and (
                not dev_id or device.deviceid == dev_id
            ):
                devices.append(device)

    if len(devices) == 0:
        _LOGGER.debug("No devices found")
        return False

    data = HoneywellService(hass, client, username, password, devices[0])
    await data.update()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config.entry_id] = data
    hass.config_entries.async_setup_platforms(config, PLATFORMS)

    return True


def get_somecomfort_client(username, password):
    """Initialize the somecomfort client."""
    try:
        return somecomfort.SomeComfort(username, password)
    except somecomfort.AuthError:
        _LOGGER.error("Failed to login to honeywell account %s", username)
        return None
    except somecomfort.SomeComfortError as ex:
        raise ConfigEntryNotReady(
            "Failed to initialize the Honeywell client: "
            "Check your configuration (username, password), "
            "or maybe you have exceeded the API rate limit?"
        ) from ex


class HoneywellService:
    """Get the latest data and update."""

    def __init__(self, hass, client, username, password, device):
        """Initialize the data object."""
        self._hass = hass
        self._client = client
        self._username = username
        self._password = password
        self.device = device

    async def _retry(self) -> bool:
        """Recreate a new somecomfort client.

        When we got an error, the best way to be sure that the next query
        will succeed, is to recreate a new somecomfort client.
        """
        self._client = await self._hass.async_add_executor_job(
            get_somecomfort_client, self._username, self._password
        )

        if self._client is None:
            return False

        devices = [
            device
            for location in self._client.locations_by_id.values()
            for device in location.devices_by_id.values()
            if device.name == self.device.name
        ]

        if len(devices) != 1:
            _LOGGER.error("Failed to find device %s", self.device.name)
            return False

        self.device = devices[0]
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self) -> None:
        """Update the state."""
        retries = 3
        while retries > 0:
            try:
                await self._hass.async_add_executor_job(self.device.refresh)
                break
            except (
                somecomfort.client.APIRateLimited,
                OSError,
                somecomfort.client.ConnectionTimeout,
            ) as exp:
                retries -= 1
                if retries == 0:
                    raise exp

                result = await self._hass.async_add_executor_job(self._retry())

                if not result:
                    raise exp

                _LOGGER.error("SomeComfort update failed, Retrying - Error: %s", exp)

        _LOGGER.debug(
            "latestData = %s ", self.device._data  # pylint: disable=protected-access
        )
