"""Helper functions for Android TV Remote integration."""

from functools import partial
from ipaddress import ip_address

from androidtvremote2 import AndroidTVRemote
import getmac

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.storage import STORAGE_DIR

from .const import CONF_ENABLE_IME, CONF_ENABLE_IME_DEFAULT_VALUE

AndroidTVRemoteConfigEntry = ConfigEntry[AndroidTVRemote]


def create_api(hass: HomeAssistant, host: str, enable_ime: bool) -> AndroidTVRemote:
    """Create an AndroidTVRemote instance."""
    return AndroidTVRemote(
        client_name="Home Assistant",
        certfile=hass.config.path(STORAGE_DIR, "androidtv_remote_cert.pem"),
        keyfile=hass.config.path(STORAGE_DIR, "androidtv_remote_key.pem"),
        host=host,
        loop=hass.loop,
        enable_ime=enable_ime,
    )


def get_enable_ime(entry: AndroidTVRemoteConfigEntry) -> bool:
    """Get value of enable_ime option or its default value."""
    return bool(entry.options.get(CONF_ENABLE_IME, CONF_ENABLE_IME_DEFAULT_VALUE))


async def async_get_nic_mac_address(hass: HomeAssistant, host: str) -> str | None:
    """Get the physical network interface MAC address for a host via ARP lookup."""
    try:
        ip_addr = ip_address(host)
    except ValueError:
        mac = await hass.async_add_executor_job(
            partial(getmac.get_mac_address, hostname=host)
        )
    else:
        if ip_addr.version == 4:
            mac = await hass.async_add_executor_job(
                partial(getmac.get_mac_address, ip=host)
            )
        else:
            mac = await hass.async_add_executor_job(
                partial(getmac.get_mac_address, ip6=str(ip_addr))
            )
    if mac:
        return format_mac(mac)
    return None

