"""The MyIO Valet Mega integration."""
# from homeassistant.components.myio_valet_mega.comms_thread import CommsThread
from datetime import timedelta
import logging

from myio.comms_thread import CommsThread
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from .const import CONF_PORT_APP, CONF_REFRESH_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    "climate",
    "cover",
    "light",
    "sensor",
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME, default="myIO-Server"): str,
                vol.Required(CONF_HOST, default="192.168.1.170"): str,
                vol.Required(CONF_PORT, default="80"): int,
                vol.Required(CONF_PORT_APP, default="843"): int,
                vol.Required(CONF_USERNAME, default="admin"): str,
                vol.Required(CONF_PASSWORD, default="admin"): str,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

COMMS_THREAD = CommsThread()


async def async_setup(hass, config):
    """Set up the myIO-server component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up config entry."""
    _server_name = slugify(config_entry.data[CONF_NAME])
    _server_status = "Offline"
    hass.data[_server_name] = {}
    hass.states.async_set(f"{_server_name}.state", _server_status)
    try:
        _refresh_timer = config_entry.options[CONF_REFRESH_TIME]
    except Exception as ex:
        _LOGGER.debug(ex)
        _refresh_timer = 4

    def server_status():
        """Return the server status."""
        return hass.states.get(f"{_server_name}.state").state

    def server_data():
        """Return the server data dictionary database."""
        return hass.data[_server_name]

    async def setup_config_entries():
        """Set up myIO platforms with config entry."""

        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, component)
            )

        # Use `hass.async_add_job` to avoid a circular dependency
        # between the platform and the component
        for component in PLATFORMS:
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(config_entry, component)
            )

    async def async_update_data():
        """Fetch data from API endpoint."""

        was_offline = False

        if server_status() == "Offline":
            was_offline = True
            for component in PLATFORMS:
                await hass.config_entries.async_forward_entry_unload(
                    config_entry, component
                )

        [hass.data[_server_name], _server_status] = await COMMS_THREAD.send(
            server_data=server_data(),
            server_status=server_status(),
            config_entry=config_entry,
            _post=None,
        )

        hass.states.async_set(f"{_server_name}.state", _server_status)

        if server_status().startswith("Online") and was_offline:
            await setup_config_entries()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.pip
        name=f"{_server_name} status",
        update_method=async_update_data,
        # Polling interval.
        update_interval=timedelta(seconds=_refresh_timer),
    )
    await coordinator.async_refresh()

    return True


async def async_unload_entry(
    hass, config_entry, async_add_devices
):  # async_add_devices because platforms
    """Unload a config entry."""
    for component in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, component)
    return True
