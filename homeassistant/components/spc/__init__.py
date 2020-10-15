"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""
import logging

from pyspcwebgw import SpcWebGateway
from pyspcwebgw.area import Area
from pyspcwebgw.zone import Zone
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

CONF_WS_URL = "ws_url"
CONF_API_URL = "api_url"

DOMAIN = "spc"

SIGNAL_UPDATE_ALARM = "spc_update_alarm_{}"
SIGNAL_UPDATE_SENSOR = "spc_update_sensor_{}"
PLATFORMS = ["alarm_control_panel", "binary_sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                cv.deprecated(CONF_WS_URL),
                cv.deprecated(CONF_API_URL),
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Old way to set up SPC, import config."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_API_URL: conf[CONF_API_URL],
                CONF_WS_URL: conf[CONF_WS_URL],
            },
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up the SPC component."""

    config = entry.data

    async def async_update_callback(spc_object):
        if isinstance(spc_object, Area):
            async_dispatcher_send(hass, SIGNAL_UPDATE_ALARM.format(spc_object.id))
        elif isinstance(spc_object, Zone):
            async_dispatcher_send(hass, SIGNAL_UPDATE_SENSOR.format(spc_object.id))

    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)

    client = SpcWebGateway(
        loop=hass.loop,
        session=session,
        api_url=config[CONF_API_URL],
        ws_url=config[CONF_WS_URL],
        async_callback=async_update_callback,
    )

    hass.data[DOMAIN][entry.entry_id] = client

    if not await client.async_load_parameters():
        _LOGGER.error("Failed to load area/zone information from SPC")
        return False

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # Start listening for incoming events over websocket.
    client.start()

    return True
