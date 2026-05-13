"""The Monarch Money integration."""

from typedmonarchmoney import TypedMonarchMoney

from homeassistant.components.recorder.statistics import (
    async_update_statistics_metadata,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import DATA_INSTANCE

from .const import MONARCH_MONEY_CURRENCY
from .coordinator import MonarchMoneyConfigEntry, MonarchMoneyDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> bool:
    """Set up Monarch Money from a config entry."""
    monarch_client = TypedMonarchMoney(token=entry.data.get(CONF_TOKEN))

    mm_coordinator = MonarchMoneyDataUpdateCoordinator(hass, entry, monarch_client)
    await mm_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = mm_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> bool:
    """Migrate old config entries."""
    if entry.version == 1 and entry.minor_version < 2:
        _async_migrate_statistics_currency(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


def _async_migrate_statistics_currency(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> None:
    """Migrate monetary sensor statistics from '$' to USD.

    Prior versions used CURRENCY_DOLLAR ('$') which is invalid for
    device_class=MONETARY sensors. This migrates existing statistics
    to use the proper ISO 4217 currency code.
    """
    if DATA_INSTANCE not in hass.data:
        return

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    for entity_entry in entries:
        if (
            entity_entry.domain == SENSOR_DOMAIN
            and entity_entry.original_device_class == SensorDeviceClass.MONETARY
        ):
            async_update_statistics_metadata(
                hass,
                entity_entry.entity_id,
                new_unit_of_measurement=MONARCH_MONEY_CURRENCY,
                new_unit_class=None,
            )


async def async_unload_entry(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
