"""The sms component."""
import asyncio
from asyncio import get_running_loop
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SMS_GATEWAY
from .gateway import create_sms_gateway

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.isdevice})},
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Configure Gammu state machine."""
    hass.data.setdefault(DOMAIN, {})
    sms_config = config.get(DOMAIN, {})
    if not sms_config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=sms_config,
        )
    )

    return True


def notify_incoming_sms(message):
    """Notify hass when an incoming SMS message is received."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configure Gammu state machine."""

    entry_id = entry.entry_id
    hass.data[DOMAIN].setdefault(entry_id, {})

    device = entry.data[CONF_DEVICE]
    config = dict(Device=device, Connection="at")
    loop = get_running_loop()
    gateway = await create_sms_gateway(config, loop, notify_incoming_sms)
    if gateway:
        hass.data[DOMAIN][SMS_GATEWAY] = gateway
        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )
        return True
    else:
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if SMS_GATEWAY in hass.data[DOMAIN]:
            gateway = hass.data[DOMAIN][SMS_GATEWAY]
            hass.data[DOMAIN].pop(SMS_GATEWAY)
            await gateway.TerminateAsync()

    return unload_ok
