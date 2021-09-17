"""The Oocsi for HomeAssistant integration."""
from __future__ import annotations

from oocsi import OOCSI, OOCSIDisconnect


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = "prototype"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oocsi for HomeAssistant from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    try:
        oocsi = OOCSI(name, host, port)
    except OOCSIDisconnect as error:


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

def async_send(
    hass: HomeAssistant, topic: Any, payload) -> None:
    oocsi.send(topic, payload)

def handleEvent(sender, recipient, event):
  print(event['color'])

def async_receive(
    hass: HomeAssistant, topic: Any, payload) -> None:
    oocsi.subscribe(topic, handleEvent)
