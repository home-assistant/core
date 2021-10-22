"""The venstar component."""
import asyncio

from venstarcolortouch import VenstarColorTouch

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)

from .const import _LOGGER, CONF_HUMIDIFIER, DOMAIN

PLATFORMS = ["climate"]


async def async_setup_entry(hass, config):
    """Set up the Venstar thermostat."""
    username = config.data.get(CONF_USERNAME)
    password = config.data.get(CONF_PASSWORD)
    pin = config.data.get(CONF_PIN)
    host = config.data[CONF_HOST]
    timeout = config.data.get(CONF_TIMEOUT)
    protocol = "https" if config.data[CONF_SSL] else "http"
    humidifier = config.data.get(CONF_HUMIDIFIER)

    client = VenstarColorTouch(
        addr=host,
        timeout=timeout,
        user=username,
        password=password,
        pin=pin,
        proto=protocol,
    )

    data = VenstarData(hass, config, client, humidifier)
    try:
        await data.async_update()
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Unable to connect to thermostat")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config.entry_id] = client
    hass.config_entries.async_setup_platforms(config, PLATFORMS)

    return True


async def async_unload_entry(hass, config):
    """Unload the config config and platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok


class VenstarData:
    """Get the latest data and update."""

    def __init__(self, hass, config, client, humidifier):
        """Initialize the data object."""
        self._hass = hass
        self._config = config
        self._client = client
        self._humidifier = humidifier

    async def async_update(self):
        """Update the state."""
        info_success = await self._hass.async_add_executor_job(self._client.update_info)
        await asyncio.sleep(3)
        sensor_success = await self._hass.async_add_executor_job(
            self._client.update_sensors
        )
        if not info_success or not sensor_success:
            _LOGGER.error("Failed to update data")

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._client.name

    @property
    def unique_id(self):
        """Set unique_id for this entity."""
        # pylint: disable=protected-access
        return f"{self._client.name}-{self._client._type}"

    @property
    def device_info(self):
        """Return the device information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._client.name)},
            "name": self._client.name,
            "manufacturer": "Venstar",
            # pylint: disable=protected-access
            "model": f"{self._client.model}-{self._client._type}",
            # pylint: disable=protected-access
            "sw_version": self._client._api_ver,
        }
