"""Support for Velbus devices."""
from __future__ import annotations

from contextlib import suppress
import logging
import os
import shutil

from velbusaio.controller import Velbus
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_INTERFACE,
    CONF_MEMO_TEXT,
    DOMAIN,
    SERVICE_CLEAR_CACHE,
    SERVICE_SCAN,
    SERVICE_SET_MEMO_TEXT,
    SERVICE_SYNC,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def velbus_connect_task(
    controller: Velbus, hass: HomeAssistant, entry_id: str
) -> None:
    """Task to offload the long running connect."""
    await controller.connect()


def _migrate_device_identifiers(hass: HomeAssistant, entry_id: str) -> None:
    """Migrate old device indentifiers."""
    dev_reg = device_registry.async_get(hass)
    devices: list[DeviceEntry] = device_registry.async_entries_for_config_entry(
        dev_reg, entry_id
    )
    for device in devices:
        old_identifier = list(next(iter(device.identifiers)))
        if len(old_identifier) > 2:
            new_identifier = {(old_identifier.pop(0), old_identifier.pop(0))}
            _LOGGER.debug(
                "migrate identifier '%s' to '%s'", device.identifiers, new_identifier
            )
            dev_reg.async_update_device(device.id, new_identifiers=new_identifier)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with velbus."""
    hass.data.setdefault(DOMAIN, {})

    controller = Velbus(
        entry.data[CONF_PORT],
        cache_dir=hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
    )
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]["cntrl"] = controller
    hass.data[DOMAIN][entry.entry_id]["tsk"] = hass.async_create_task(
        velbus_connect_task(controller, hass, entry.entry_id)
    )

    _migrate_device_identifiers(hass, entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if hass.services.has_service(DOMAIN, SERVICE_SCAN):
        return True

    def check_entry_id(interface: str) -> str:
        for entry in hass.config_entries.async_entries(DOMAIN):
            if "port" in entry.data and entry.data["port"] == interface:
                return entry.entry_id
        raise vol.Invalid(
            "The interface provided is not defined as a port in a Velbus integration"
        )

    async def scan(call: ServiceCall) -> None:
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].scan()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN,
        scan,
        vol.Schema({vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id)}),
    )

    async def syn_clock(call: ServiceCall) -> None:
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].sync_clock()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC,
        syn_clock,
        vol.Schema({vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id)}),
    )

    async def set_memo_text(call: ServiceCall) -> None:
        """Handle Memo Text service call."""
        memo_text = call.data[CONF_MEMO_TEXT]
        memo_text.hass = hass
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].get_module(
            call.data[CONF_ADDRESS]
        ).set_memo_text(memo_text.async_render())

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MEMO_TEXT,
        set_memo_text,
        vol.Schema(
            {
                vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                vol.Required(CONF_ADDRESS): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=255)
                ),
                vol.Optional(CONF_MEMO_TEXT, default=""): cv.template,
            }
        ),
    )

    async def clear_cache(call: ServiceCall) -> None:
        """Handle a clear cache service call."""
        # clear the cache
        with suppress(FileNotFoundError):
            if call.data[CONF_ADDRESS]:
                await hass.async_add_executor_job(
                    os.unlink,
                    hass.config.path(
                        STORAGE_DIR,
                        f"velbuscache-{call.data[CONF_INTERFACE]}/{call.data[CONF_ADDRESS]}.p",
                    ),
                )
            else:
                await hass.async_add_executor_job(
                    shutil.rmtree,
                    hass.config.path(
                        STORAGE_DIR, f"velbuscache-{call.data[CONF_INTERFACE]}/"
                    ),
                )
        # call a scan to repopulate
        await scan(call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        clear_cache,
        vol.Schema(
            {
                vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                vol.Optional(CONF_ADDRESS): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=255)
                ),
            }
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload (close) the velbus connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.data[DOMAIN][entry.entry_id]["cntrl"].stop()
    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
        hass.services.async_remove(DOMAIN, SERVICE_SCAN)
        hass.services.async_remove(DOMAIN, SERVICE_SYNC)
        hass.services.async_remove(DOMAIN, SERVICE_SET_MEMO_TEXT)
        hass.services.async_remove(DOMAIN, SERVICE_CLEAR_CACHE)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the velbus entry, so we also have to cleanup the cache dir."""
    await hass.async_add_executor_job(
        shutil.rmtree,
        hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
    )
