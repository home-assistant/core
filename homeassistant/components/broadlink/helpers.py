"""Helper functions for the Broadlink integration."""
from base64 import b64decode

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


def data_packet(value):
    """Decode a data packet given for a Broadlink remote."""
    value = cv.string(value)
    extra = len(value) % 4
    if extra > 0:
        value = value + ("=" * (4 - extra))
    return b64decode(value)


def mac_address(mac):
    """Validate and convert a MAC address to bytes."""
    mac = cv.string(mac)
    if len(mac) == 17:
        mac = "".join(mac[i : i + 2] for i in range(0, 17, 3))
    elif len(mac) == 14:
        mac = "".join(mac[i : i + 4] for i in range(0, 14, 5))
    elif len(mac) != 12:
        raise ValueError("Invalid MAC address")
    return bytes.fromhex(mac)


def format_mac(mac):
    """Format a MAC address."""
    return ":".join([format(octet, "02x") for octet in mac])


def import_device(hass, host):
    """Create a config flow for a device."""
    configured_hosts = {
        entry.data.get(CONF_HOST) for entry in hass.config_entries.async_entries(DOMAIN)
    }

    if host not in configured_hosts:
        task = hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: host},
        )
        hass.async_create_task(task)
