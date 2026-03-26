"""The snmp component."""

import logging

from pysnmp.error import PySnmpError
from pysnmp.smi.error import WrongValueError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import SnmpUpdateCoordinator
from .util import async_get_snmp_engine

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

type SnmpConfigEntry = ConfigEntry[SnmpUpdateCoordinator]

__all__ = ["async_get_snmp_engine"]


async def async_setup_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> bool:
    """Set up SNMP from a config entry."""
    coordinator = SnmpUpdateCoordinator(hass, entry)

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
        name=coordinator.sys_name or entry.data[CONF_HOST],
        sw_version=coordinator.sw_version,
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This line shuts down the platforms we started in 'async_setup_entry'.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
