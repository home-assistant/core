"""The Monarch Money integration."""

from __future__ import annotations

from typedmonarchmoney import TypedMonarchMoney

from homeassistant.components.recorder.statistics import (
    async_update_statistics_metadata,
)
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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

    # Migrate statistics from "$" to proper ISO currency code
    _async_migrate_statistics_currency(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _async_migrate_statistics_currency(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> None:
    """Migrate monetary sensor statistics from '$' to configured currency.

    Prior versions used CURRENCY_DOLLAR ('$') which is invalid for
    device_class=MONETARY sensors. This migrates existing statistics
    to use the proper ISO 4217 currency code from HA config.
    """
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    currency = hass.config.currency

    for entity_entry in entries:
        # Only migrate sensor entities with monetary device class
        if (
            entity_entry.domain == "sensor"
            and entity_entry.original_device_class == "monetary"
        ):
            async_update_statistics_metadata(
                hass,
                entity_entry.entity_id,
                new_unit_of_measurement=currency,
                new_unit_class=None,
            )


async def async_unload_entry(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
