"""The sky_hub component."""
from pyskyqhub.skyq_hub import SkyQHub

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS = ["device_tracker"]


async def async_setup(hass, config):
    """Set up the sky)hub component."""
    conf = config[DOMAIN][0]

    host = conf.get(CONF_HOST, "192.168.1.254")
    websession = async_get_clientsession(hass)
    hub = SkyQHub(websession, host)
    await hub.async_connect()

    return hub.success_init
