"""The broadlink component."""
import asyncio
from base64 import b64decode, b64encode
import logging
import re

from datetime import timedelta
import voluptuous as vol

from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

from .const import DOMAIN, SERVICE_LEARN, SERVICE_SEND

_LOGGER = logging.getLogger(__name__)


def ipv4_address(value):
    """Validate an ipv4 address."""
    regex = re.compile(r'^\d+\.\d+\.\d+\.\d+$')
    if not regex.match(value):
        raise vol.Invalid('Invalid Ipv4 address, expected a.b.c.d')
    return value


def data_packet(value):
    """Decode a data packet given for broadlink."""
    return b64decode(cv.string(value))


SERVICE_SEND_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): ipv4_address,
    vol.Required('packet'): vol.All(cv.ensure_list, [data_packet])
})

SERVICE_LEARN_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): ipv4_address,
})


def async_setup_service(hass, host, device):
    """Register a device for given host for use in services."""
    hass.data.setdefault(DOMAIN, {})[host] = device

    if not hass.services.has_service(DOMAIN, SERVICE_LEARN):

        async def _learn_command(call):
            """Learn a packet from remote."""
            device = hass.data[DOMAIN][call.data[CONF_HOST]]
            await hass.async_add_job(device.enter_learning)

            _LOGGER.info("Press the key you want Home Assistant to learn")
            start_time = utcnow()
            while (utcnow() - start_time) < timedelta(seconds=20):
                packet = await hass.async_add_job(
                    device.check_data)
                if packet:
                    data = b64encode(packet).decode('utf8')
                    log_msg = "Received packet is: {}".\
                              format(data)
                    _LOGGER.info(log_msg)
                    hass.components.persistent_notification.async_create(
                        log_msg, title='Broadlink switch')
                    return
                await asyncio.sleep(1, loop=hass.loop)
            _LOGGER.error("Did not received any signal")
            hass.components.persistent_notification.async_create(
                "Did not received any signal", title='Broadlink switch')

        hass.services.async_register(
            DOMAIN, SERVICE_LEARN, _learn_command,
            schema=SERVICE_LEARN_SCHEMA)

    if not hass.services.has_service(DOMAIN, SERVICE_SEND):

        async def _send_packet(call):
            """Send a packet."""
            device = hass.data[DOMAIN][call.data[CONF_HOST]]
            packets = call.data.get('packet', [])
            for packet in packets:
                await hass.async_add_job(
                    device.send_data, packet)
        hass.services.async_register(
            DOMAIN, SERVICE_SEND, _send_packet,
            schema=SERVICE_SEND_SCHEMA)
