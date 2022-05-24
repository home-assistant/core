"""The Samsung TV integration."""
from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import socket
from typing import Any
from urllib.parse import urlparse

import getmac
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import ConfigType

from .bridge import (
    SamsungTVBridge,
    async_get_device_info,
    mac_from_device_info,
    model_requires_encryption,
)
from .const import (
    CONF_ON_ACTION,
    CONF_SESSION_ID,
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DEFAULT_NAME,
    DOMAIN,
    ENTRY_RELOAD_COOLDOWN,
    LEGACY_PORT,
    LOGGER,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_LEGACY,
    UPNP_SVC_MAIN_TV_AGENT,
    UPNP_SVC_RENDERING_CONTROL,
)


def ensure_unique_hosts(value: dict[Any, Any]) -> dict[Any, Any]:
    """Validate that all configs have a unique host."""
    vol.Schema(vol.Unique("duplicate host entries found"))(
        [entry[CONF_HOST] for entry in value]
    )
    return value


PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                cv.deprecated(CONF_PORT),
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_PORT): cv.port,
                        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                    }
                ),
            ],
            ensure_unique_hosts,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Samsung TV integration."""
    hass.data[DOMAIN] = {}
    if DOMAIN not in config:
        return True

    for entry_config in config[DOMAIN]:
        ip_address = await hass.async_add_executor_job(
            socket.gethostbyname, entry_config[CONF_HOST]
        )
        hass.data[DOMAIN][ip_address] = {
            CONF_ON_ACTION: entry_config.get(CONF_ON_ACTION)
        }
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=entry_config,
            )
        )
    return True


@callback
def _async_get_device_bridge(
    hass: HomeAssistant, data: dict[str, Any]
) -> SamsungTVBridge:
    """Get device bridge."""
    return SamsungTVBridge.get_bridge(
        hass,
        data[CONF_METHOD],
        data[CONF_HOST],
        data[CONF_PORT],
        data,
    )


class DebouncedEntryReloader:
    """Reload only after the timer expires."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init the debounced entry reloader."""
        self.hass = hass
        self.entry = entry
        self.token = self.entry.data.get(CONF_TOKEN)
        self._debounced_reload = Debouncer(
            hass,
            LOGGER,
            cooldown=ENTRY_RELOAD_COOLDOWN,
            immediate=False,
            function=self._async_reload_entry,
        )

    async def async_call(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Start the countdown for a reload."""
        if (new_token := entry.data.get(CONF_TOKEN)) != self.token:
            LOGGER.debug("Skipping reload as its a token update")
            self.token = new_token
            return  # Token updates should not trigger a reload
        LOGGER.debug("Calling debouncer to get a reload after cooldown")
        await self._debounced_reload.async_call()

    @callback
    def async_cancel(self) -> None:
        """Cancel any pending reload."""
        self._debounced_reload.async_cancel()

    async def _async_reload_entry(self) -> None:
        """Reload entry."""
        LOGGER.debug("Reloading entry %s", self.entry.title)
        await self.hass.config_entries.async_reload(self.entry.entry_id)


async def _async_update_ssdp_locations(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update ssdp locations from discovery cache."""
    updates = {}
    for ssdp_st, key in (
        (UPNP_SVC_RENDERING_CONTROL, CONF_SSDP_RENDERING_CONTROL_LOCATION),
        (UPNP_SVC_MAIN_TV_AGENT, CONF_SSDP_MAIN_TV_AGENT_LOCATION),
    ):
        for discovery_info in await ssdp.async_get_discovery_info_by_st(hass, ssdp_st):
            location = discovery_info.ssdp_location
            host = urlparse(location).hostname
            if host == entry.data[CONF_HOST]:
                updates[key] = location
                break

    if updates:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Samsung TV platform."""

    # Initialize bridge
    if entry.data.get(CONF_METHOD) == METHOD_ENCRYPTED_WEBSOCKET:
        if not entry.data.get(CONF_TOKEN) or not entry.data.get(CONF_SESSION_ID):
            raise ConfigEntryAuthFailed(
                "Token and session id are required in encrypted mode"
            )
    bridge = await _async_create_bridge_with_updated_data(hass, entry)

    # Ensure updates get saved against the config_entry
    @callback
    def _update_config_entry(updates: Mapping[str, Any]) -> None:
        """Update config entry with the new token."""
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})

    bridge.register_update_config_entry_callback(_update_config_entry)

    async def stop_bridge(event: Event) -> None:
        """Stop SamsungTV bridge connection."""
        LOGGER.debug("Stopping SamsungTVBridge %s", bridge.host)
        await bridge.async_close_remote()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_bridge)
    )

    await _async_update_ssdp_locations(hass, entry)

    # We must not await after we setup the reload or there
    # will be a race where the config flow will see the entry
    # as not loaded and may reload it
    debounced_reloader = DebouncedEntryReloader(hass, entry)
    entry.async_on_unload(debounced_reloader.async_cancel)
    entry.async_on_unload(entry.add_update_listener(debounced_reloader.async_call))

    hass.data[DOMAIN][entry.entry_id] = bridge
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def _async_create_bridge_with_updated_data(
    hass: HomeAssistant, entry: ConfigEntry
) -> SamsungTVBridge:
    """Create a bridge object and update any missing data in the config entry."""
    updated_data: dict[str, str | int] = {}
    host: str = entry.data[CONF_HOST]
    port: int | None = entry.data.get(CONF_PORT)
    method: str | None = entry.data.get(CONF_METHOD)
    load_info_attempted = False
    info: dict[str, Any] | None = None

    if not port or not method:
        LOGGER.debug("Attempting to get port or method for %s", host)
        if method == METHOD_LEGACY:
            port = LEGACY_PORT
        else:
            # When we imported from yaml we didn't setup the method
            # because we didn't know it
            _result, port, method, info = await async_get_device_info(hass, host)
            load_info_attempted = True
            if not port or not method:
                raise ConfigEntryNotReady(
                    "Failed to determine connection method, make sure the device is on."
                )

        LOGGER.info("Updated port to %s and method to %s for %s", port, method, host)
        updated_data[CONF_PORT] = port
        updated_data[CONF_METHOD] = method

    bridge = _async_get_device_bridge(hass, {**entry.data, **updated_data})

    mac: str | None = entry.data.get(CONF_MAC)
    model: str | None = entry.data.get(CONF_MODEL)
    if (not mac or not model) and not load_info_attempted:
        info = await bridge.async_device_info()

    if not mac:
        LOGGER.debug("Attempting to get mac for %s", host)
        if info:
            mac = mac_from_device_info(info)

        if not mac:
            mac = await hass.async_add_executor_job(
                partial(getmac.get_mac_address, ip=host)
            )

        if mac:
            LOGGER.info("Updated mac to %s for %s", mac, host)
            updated_data[CONF_MAC] = mac
        else:
            LOGGER.info("Failed to get mac for %s", host)

    if not model:
        LOGGER.debug("Attempting to get model for %s", host)
        if info:
            model = info.get("device", {}).get("modelName")
            if model:
                LOGGER.info("Updated model to %s for %s", model, host)
                updated_data[CONF_MODEL] = model

    if model_requires_encryption(model) and method != METHOD_ENCRYPTED_WEBSOCKET:
        LOGGER.info(
            "Detected model %s for %s. Some televisions from H and J series use "
            "an encrypted protocol but you are using %s which may not be supported",
            model,
            host,
            method,
        )

    if updated_data:
        data = {**entry.data, **updated_data}
        hass.config_entries.async_update_entry(entry, data=data)

    return bridge


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        bridge: SamsungTVBridge = hass.data[DOMAIN][entry.entry_id]
        LOGGER.debug("Stopping SamsungTVBridge %s", bridge.host)
        await bridge.async_close_remote()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    version = config_entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Unique ID format changed, so delete and re-import:
    if version == 1:
        dev_reg = dr.async_get(hass)
        dev_reg.async_clear_config_entry(config_entry.entry_id)

        en_reg = er.async_get(hass)
        en_reg.async_clear_config_entry(config_entry.entry_id)

        version = config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry)
    LOGGER.debug("Migration to version %s successful", version)

    return True
