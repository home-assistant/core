"""The snmp component."""

import logging

from pysnmp.error import PySnmpError
from pysnmp.smi.error import WrongValueError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_BASEOID,
    CONF_CONTEXT_NAME,
    CONF_VERSION,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    DOMAIN,
)
from .coordinator import SnmpUpdateCoordinator
from .util import (
    async_create_request_cmd_args,
    async_create_transport_target,
    async_get_snmp_engine,
    create_auth_data,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

type SnmpConfigEntry = ConfigEntry[SnmpUpdateCoordinator]

__all__ = ["async_get_snmp_engine"]


async def async_setup_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> bool:
    """Set up SNMP from a config entry."""
    host = entry.data[CONF_HOST]
    baseoid = entry.data[CONF_BASEOID]
    version = entry.data.get(CONF_VERSION, DEFAULT_VERSION)
    context_name = entry.data.get(CONF_CONTEXT_NAME)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    auth_data = create_auth_data(entry.data, version)
    try:
        target = await async_create_transport_target(host, port, DEFAULT_TIMEOUT)
    except PySnmpError as err:
        raise ConfigEntryNotReady(f"Cannot reach SNMP host: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during SNMP target creation")
        raise ConfigEntryNotReady(
            f"Unexpected error during SNMP target creation: {err}"
        ) from err

    request_args = await async_create_request_cmd_args(
        hass,
        auth_data,
        target,
        baseoid,
        context_name,
    )

    coordinator = SnmpUpdateCoordinator(hass, entry, request_args)

    try:
        await coordinator.async_config_entry_first_refresh()
    except WrongValueError as err:
        raise ConfigEntryAuthFailed(
            f"Invalid authentication credentials or protocols: {err}"
        ) from err
    except PySnmpError as err:
        raise ConfigEntryNotReady(f"Router unreachable: {err}") from err

    if coordinator.sys_name:
        hass.config_entries.async_update_entry(entry, title=coordinator.sys_name)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=coordinator.manufacturer,
        model=coordinator.model,
        name=coordinator.sys_name or host,
        sw_version=coordinator.sw_version,
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This line shuts down the platforms we started in 'async_setup_entry'.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
