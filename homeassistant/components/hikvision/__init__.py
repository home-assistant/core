"""The hikvision component."""
from __future__ import annotations

from pyhik.hikvision import HikCamera

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


class HikvisionData:
    """Hikvision device event stream object."""

    def __init__(self, hass, url, port, name, username, password):
        """Initialize the data object."""
        self._url = url
        self._port = port
        self._name = name
        self._username = username
        self._password = password

        # Establish camera
        self.camdata = HikCamera(self._url, self._port, self._username, self._password)

        if self._name is None:
            self._name = self.camdata.get_name

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.stop_hik)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self.start_hik)

    def stop_hik(self, event):
        """Shutdown Hikvision subscriptions and subscription thread on exit."""
        self.camdata.disconnect()

    def start_hik(self, event):
        """Start Hikvision event stream thread."""
        self.camdata.start_stream()

    @property
    def sensors(self):
        """Return list of available sensors and their states."""
        return self.camdata.current_event_states

    @property
    def cam_id(self):
        """Return device id."""
        return self.camdata.get_id

    @property
    def name(self):
        """Return device name."""
        return self._name

    @property
    def type(self):
        """Return device type."""
        return self.camdata.get_type

    def get_attributes(self, sensor, channel):
        """Return attribute list for sensor/channel."""
        return self.camdata.fetch_attributes(sensor, channel)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import configuration from yaml."""

    # check if already configured
    if hass.config_entries.async_entries(DOMAIN):
        return True

    # Iterate all entries for notify to only get Slack
    for entry in config.get(Platform.BINARY_SENSOR, []):
        if entry[CONF_PLATFORM] == DOMAIN:
            user_input = {
                "host": entry["host"],
                "username": entry["username"],
                "password": entry["password"],
                "ssl": entry.get("ssl", False),
                "port": entry.get("port", 80),
                "name": entry.get("name", "hikvision"),
            }
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=user_input
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hikvision from a config entry."""
    protocol = "https" if entry.data.get(CONF_SSL) else "http"
    host = entry.data.get(CONF_HOST)
    url = f"{protocol}://{host}"
    port = entry.data.get(CONF_PORT)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    name = entry.data.get(CONF_NAME)

    hass.data.setdefault(DOMAIN, {})
    # api = HikvisionData(url, port, name, username, password)
    api = await hass.async_add_executor_job(
        HikvisionData, hass, url, port, name, username, password
    )
    hass.data[DOMAIN][entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        api = hass.data[DOMAIN].pop(entry.entry_id)
        api.stop_hik(None)

    return unload_ok
