"""The fritzbox_callmonitor component."""
import asyncio

from fritzconnection.lib.fritzphonebook import FritzPhonebook

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import DOMAIN, PLATFORMS


async def async_setup(hass, config):
    """Set up the AVM Fritz!Box integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up the AVM Fritz!Box platforms."""
    phonebook = FritzPhonebook(
        address=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    hass.data[DOMAIN][entry.entry_id] = phonebook

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unloading the AVM Fritz!Box platforms."""

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

    return unload_ok
