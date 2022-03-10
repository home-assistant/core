"""The Samsung TV integration."""
from __future__ import annotations

from functools import partial
import socket
from typing import Any

import getmac
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .bridge import SamsungTVBridge, async_get_device_info, mac_from_device_info
from .const import (
    CONF_MODEL,
    CONF_ON_ACTION,
    CONF_SESSION_ID,
    DEFAULT_NAME,
    DOMAIN,
    LEGACY_PORT,
    LOGGER,
    METHOD_LEGACY,
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
        data.get(CONF_TOKEN),
        data.get(CONF_SESSION_ID),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Samsung TV platform."""

    # Initialize bridge
    bridge = await _async_create_bridge_with_updated_data(hass, entry)

    # Ensure new token gets saved against the config_entry
    @callback
    def _update_token() -> None:
        """Update config entry with the new token."""
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKEN: bridge.token}
        )

    bridge.register_new_token_callback(_update_token)

    async def stop_bridge(event: Event) -> None:
        """Stop SamsungTV bridge connection."""
        LOGGER.debug("Stopping SamsungTVBridge %s", bridge.host)
        await bridge.async_close_remote()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_bridge)
    )

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
            port, method, info = await async_get_device_info(hass, None, host)
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

    if model and len(model) > 4 and model[4] in ("H", "J"):
        LOGGER.info(
            "Detected model %s for %s. Some televisions from H and J series use "
            "an encrypted protocol that may not be supported in this integration",
            model,
            host,
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
        dev_reg = await hass.helpers.device_registry.async_get_registry()
        dev_reg.async_clear_config_entry(config_entry)

        en_reg = await hass.helpers.entity_registry.async_get_registry()
        en_reg.async_clear_config_entry(config_entry)

        version = config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry)
    LOGGER.debug("Migration to version %s successful", version)

    return True
