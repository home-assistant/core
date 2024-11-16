"""The zcc integration."""

from __future__ import annotations

import logging

from zcc import ControlPoint, ControlPointDescription, ControlPointError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_connect_to_controller(
    host: str, port: int, fast: bool = False
) -> ControlPoint | None:
    """Connect to Zimi Cloud Controller with defined parameters."""

    _LOGGER.debug("Connecting to %s:%d", host, port)

    try:
        api = ControlPoint(
            description=ControlPointDescription(
                host=host,
                port=port,
            )
        )
        await api.connect(fast=fast)

    except ControlPointError as error:
        _LOGGER.error("Connection failed: %s", error)
        raise ConfigEntryNotReady(error) from error

    if api.ready:
        _LOGGER.debug("Connected")

        if not fast:
            api.start_watchdog()
            _LOGGER.debug("Started watchdog")

        return api

    msg = "Connection failed: not ready"
    _LOGGER.error(msg=msg)

    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to Zimi Controller and register device."""
    _LOGGER.debug("Zimi setup starting")

    try:
        api = await async_connect_to_controller(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
        )

    except ControlPointError as error:
        _LOGGER.error("Initiation failed: %s", error)
        raise ConfigEntryNotReady(error) from error

    if api:
        _LOGGER.debug("\n%s", api.describe())

        entry.runtime_data = api

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, api.mac)},
            manufacturer=api.brand,
            name=f"Zimi({api.host}:{api.port})",
            model=api.product,
            model_id="Zimi Cloud Connect",
            hw_version=f"{api.mac}",
            sw_version=f"{api.firmware_version} (API {api.api_version})",
        )

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    else:
        msg = "Zimi setup failed: not ready"
        _LOGGER.error(msg=msg)
        raise ConfigEntryNotReady(msg)

    _LOGGER.debug("Zimi setup complete")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    api = entry.runtime_data
    if api:
        api.disconnect()

    device_registry = dr.async_get(hass)

    zimi_device = device_registry.async_get_device(identifiers={(DOMAIN, api.mac)})

    assert zimi_device is not None

    device_registry.async_remove_device(device_id=zimi_device.id)

    return False
