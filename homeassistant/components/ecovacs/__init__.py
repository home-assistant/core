"""Support for Ecovacs vacuums."""
import asyncio
from functools import partial

from sucks import EcoVacsAPI, VacBot

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)

from .const import (
    CONF_CONTINENT,
    CONF_COUNTRY,
    DATA_REMOVE_LISTENER,
    DEVICES,
    DOMAIN,
    ECOVACS_ATTR_DEVICE_ID,
    ECOVACS_ATTR_NAME,
    LOGGER,
    PLATFORMS,
)


async def async_setup(hass, config):
    """Set up the Ecovacs integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up the Ecovacs platforms."""

    def stop_ecovacs(event):
        """Shut down open connections to Ecovacs XMPP server."""
        if not hass.data.get(DOMAIN):
            return

        devices = hass.data[DOMAIN][entry.entry_id][DEVICES]

        for device in devices:
            LOGGER.info(
                "Shutting down connection to Ecovacs device %s",
                device.vacuum[ECOVACS_ATTR_DEVICE_ID],
            )
            device.disconnect()

    ecovacs_api = await hass.async_add_executor_job(
        partial(
            EcoVacsAPI,
            entry.data[CONF_DEVICE_ID],
            entry.data[CONF_USERNAME],
            EcoVacsAPI.md5(entry.data[CONF_PASSWORD]),
            entry.data[CONF_COUNTRY],
            entry.data[CONF_CONTINENT],
        )
    )

    vacuums = []
    devices = await hass.async_add_executor_job(ecovacs_api.devices)

    for device in devices:
        LOGGER.info(
            "Discovered Ecovacs device on account: %s with nickname %s",
            device[ECOVACS_ATTR_DEVICE_ID],
            device[ECOVACS_ATTR_NAME],
        )
        vacbot = VacBot(
            ecovacs_api.uid,
            ecovacs_api.REALM,
            ecovacs_api.resource,
            ecovacs_api.user_access_token,
            device,
            entry.data[CONF_CONTINENT],
            monitor=True,
        )
        vacuums.append(vacbot)

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, stop_ecovacs
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DEVICES: vacuums,
        DATA_REMOVE_LISTENER: remove_stop_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unloading the Ecovacs platforms."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if not unload_ok:
        return False

    hass.data[DOMAIN][entry.entry_id][DATA_REMOVE_LISTENER]()

    if hass.data[DOMAIN][entry.entry_id]:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return True
