"""Support for the Sabnzbd service."""
from pysabnzbd import SabnzbdApi, SabnzbdApiException

from homeassistant.components.sabnzbd.const import BASE_URL_FORMAT
from homeassistant.components.sabnzbd.errors import AuthenticationError
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PATH, CONF_PORT, CONF_SSL
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def get_client(hass: HomeAssistant, data):
    """Get Sabnzbd client."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    web_root = data.get(CONF_PATH)
    api_key = data[CONF_API_KEY]
    use_ssl = data[CONF_SSL]
    uri_scheme = "https" if use_ssl else "http"
    base_url = BASE_URL_FORMAT.format(uri_scheme, host, port)

    sab_api = SabnzbdApi(
        base_url,
        api_key,
        web_root=web_root,
        session=async_get_clientsession(hass, False),
    )
    try:
        await sab_api.check_available()
    except SabnzbdApiException as exception:
        _LOGGER.error("Connection to SABnzbd API failed: %s", exception.message)
        raise AuthenticationError from exception

    return sab_api
