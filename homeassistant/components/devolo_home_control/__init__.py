"""The devolo_home_control integration."""
import asyncio
from functools import partial

from devolo_home_control_api.homecontrol import HomeControl
from devolo_home_control_api.mydevolo import Mydevolo

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_HOMECONTROL, CONF_MYDEVOLO, DOMAIN, PLATFORMS


async def async_setup(hass, config):
    """Get all devices and add them to hass."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up the devolo account from a config entry."""
    conf = entry.data
    hass.data.setdefault(DOMAIN, {})
    try:
        mydevolo = Mydevolo.get_instance()
    except SyntaxError:
        mydevolo = Mydevolo()

    mydevolo.user = conf[CONF_USERNAME]
    mydevolo.password = conf[CONF_PASSWORD]
    mydevolo.url = conf[CONF_MYDEVOLO]

    credentials_valid = await hass.async_add_executor_job(mydevolo.credentials_valid)

    if not credentials_valid:
        return False

    if await hass.async_add_executor_job(mydevolo.maintenance):
        raise ConfigEntryNotReady

    gateway_ids = await hass.async_add_executor_job(mydevolo.get_gateway_ids)
    gateway_id = gateway_ids[0]

    try:
        zeroconf_instance = await zeroconf.async_get_instance(hass)
        hass.data[DOMAIN]["homecontrol"] = await hass.async_add_executor_job(
            partial(
                HomeControl,
                gateway_id=gateway_id,
                zeroconf_instance=zeroconf_instance,
                url=conf[CONF_HOMECONTROL],
            )
        )
    except ConnectionError as err:
        raise ConfigEntryNotReady from err

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    def shutdown(event):
        hass.data[DOMAIN]["homecontrol"].websocket_disconnect(
            f"websocket disconnect requested by {EVENT_HOMEASSISTANT_STOP}"
        )

    # Listen when EVENT_HOMEASSISTANT_STOP is fired
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    await hass.async_add_executor_job(
        hass.data[DOMAIN]["homecontrol"].websocket_disconnect
    )
    del hass.data[DOMAIN]["homecontrol"]
    return unload
