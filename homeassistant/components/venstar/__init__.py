"""The venstar component."""
import asyncio

from requests import RequestException
from venstarcolortouch import VenstarColorTouch

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity

from .const import _LOGGER, DOMAIN, VENSTAR_TIMEOUT

PLATFORMS = ["climate"]


async def async_setup_entry(hass, config):
    """Set up the Venstar thermostat."""
    username = config.data.get(CONF_USERNAME)
    password = config.data.get(CONF_PASSWORD)
    pin = config.data.get(CONF_PIN)
    host = config.data[CONF_HOST]
    timeout = VENSTAR_TIMEOUT
    protocol = "https" if config.data[CONF_SSL] else "http"

    client = VenstarColorTouch(
        addr=host,
        timeout=timeout,
        user=username,
        password=password,
        pin=pin,
        proto=protocol,
    )

    try:
        await hass.async_add_executor_job(client.update_info)
    except (OSError, RequestException) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to the thermostat: {ex}") from ex
    hass.data.setdefault(DOMAIN, {})[config.entry_id] = client
    hass.config_entries.async_setup_platforms(config, PLATFORMS)

    return True


async def async_unload_entry(hass, config):
    """Unload the config config and platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config.entry_id)
    return unload_ok


class VenstarEntity(Entity):
    """Get the latest data and update."""

    def __init__(self, config, client):
        """Initialize the data object."""
        self._config = config
        self._client = client

    async def async_update(self):
        """Update the state."""
        try:
            info_success = await self.hass.async_add_executor_job(
                self._client.update_info
            )
        except (OSError, RequestException) as ex:
            _LOGGER.error("Exception during info update: %s", ex)

        # older venstars sometimes cannot handle rapid sequential connections
        await asyncio.sleep(3)

        try:
            sensor_success = await self.hass.async_add_executor_job(
                self._client.update_sensors
            )
        except (OSError, RequestException) as ex:
            _LOGGER.error("Exception during sensor update: %s", ex)

        if not info_success or not sensor_success:
            _LOGGER.error("Failed to update data")

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._client.name

    @property
    def unique_id(self):
        """Set unique_id for this entity."""
        return f"{self._config.entry_id}"

    @property
    def device_info(self):
        """Return the device information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._config.entry_id)},
            "name": self._client.name,
            "manufacturer": "Venstar",
            # pylint: disable=protected-access
            "model": f"{self._client.model}-{self._client._type}",
            # pylint: disable=protected-access
            "sw_version": self._client._api_ver,
        }
