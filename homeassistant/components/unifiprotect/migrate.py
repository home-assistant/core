"""UniFi Protect data migrations."""
from __future__ import annotations

import logging

from pyunifiprotect import ProtectApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICES_THAT_ADOPT

_LOGGER = logging.getLogger(__name__)


async def async_migrate_data(
    hass: HomeAssistant, entry: ConfigEntry, protect: ProtectApiClient
) -> None:
    """Run all valid UniFi Protect data migrations."""

    _LOGGER.debug("Start Migrate: async_migrate_buttons")
    await async_migrate_buttons(hass, entry, protect)
    _LOGGER.debug("Completed Migrate: async_migrate_buttons")


async def async_migrate_buttons(
    hass: HomeAssistant, entry: ConfigEntry, protect: ProtectApiClient
) -> None:
    """
    Migrate existing Reboot button unique IDs from {device_id} to {deivce_id}_reboot.

    This allows for additional types of buttons that are outside of just a reboot button.

    Added in 2022.6.0.
    """

    registry = er.async_get(hass)
    to_migrate = []
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == Platform.BUTTON and "_" not in entity.unique_id:
            _LOGGER.debug("Button %s needs migration", entity.entity_id)
            to_migrate.append(entity)

    if len(to_migrate) == 0:
        _LOGGER.debug("No button entities need migration")
        return

    _LOGGER.info("Migrating %s reboot button entities", len(to_migrate))
    bootstrap = await protect.get_bootstrap()
    count = 0
    for button in to_migrate:
        device = None
        for model in DEVICES_THAT_ADOPT:
            attr = f"{model.value}s"
            device = getattr(bootstrap, attr).get(button.unique_id)
            if device is not None:
                break

        if device is None:
            continue

        new_unique_id = f"{device.id}_reboot"
        _LOGGER.debug(
            "Migrating entity %s (old unique_id: %s, new unique_id: %s)",
            button.entity_id,
            button.unique_id,
            new_unique_id,
        )
        try:
            registry.async_update_entity(button.entity_id, new_unique_id=new_unique_id)
        except ValueError:
            _LOGGER.warning(
                "Could not migrate entity %s (old unique_id: %s, new unique_id: %s)",
                button.entity_id,
                button.unique_id,
                new_unique_id,
            )
        else:
            count += 1

    if count < len(to_migrate):
        _LOGGER.warning("Failed to migate %s reboot buttons", len(to_migrate) - count)
    else:
        _LOGGER.info("Migrated %s reboot button entities", count)
