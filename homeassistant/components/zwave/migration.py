"""Handle migration from legacy Z-Wave to OpenZWave and Z-Wave JS."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .util import node_device_id_and_name

if TYPE_CHECKING:
    from . import ZWaveDeviceEntityValues

LEGACY_ZWAVE_MIGRATION = f"{DOMAIN}_legacy_zwave_migration"
STORAGE_WRITE_DELAY = 30
STORAGE_KEY = f"{DOMAIN}.legacy_zwave_migration"
STORAGE_VERSION = 1


class ZWaveMigrationData(TypedDict):
    """Represent the Z-Wave migration data dict."""

    node_id: int
    node_instance: int
    command_class: int
    command_class_label: str
    value_index: int
    device_id: str
    domain: str
    entity_id: str
    unique_id: str
    unit_of_measurement: str | None


@callback
def async_is_ozw_migrated(hass):
    """Return True if migration to ozw is done."""
    ozw_config_entries = hass.config_entries.async_entries("ozw")
    if not ozw_config_entries:
        return False

    ozw_config_entry = ozw_config_entries[0]  # only one ozw entry is allowed
    migrated = bool(ozw_config_entry.data.get("migrated"))
    return migrated


@callback
def async_is_zwave_js_migrated(hass):
    """Return True if migration to Z-Wave JS is done."""
    zwave_js_config_entries = hass.config_entries.async_entries("zwave_js")
    if not zwave_js_config_entries:
        return False

    migrated = any(
        config_entry.data.get("migrated") for config_entry in zwave_js_config_entries
    )
    return migrated


async def async_add_migration_entity_value(
    hass: HomeAssistant,
    entity_id: str,
    entity_values: ZWaveDeviceEntityValues,
) -> None:
    """Add Z-Wave entity value for legacy Z-Wave migration."""
    migration_handler: LegacyZWaveMigration = await get_legacy_zwave_migration(hass)
    migration_handler.add_entity_value(entity_id, entity_values)


async def async_get_migration_data(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, ZWaveMigrationData]:
    """Return Z-Wave migration data."""
    migration_handler: LegacyZWaveMigration = await get_legacy_zwave_migration(hass)
    return await migration_handler.get_data(config_entry)


@singleton(LEGACY_ZWAVE_MIGRATION)
async def get_legacy_zwave_migration(hass: HomeAssistant) -> LegacyZWaveMigration:
    """Return legacy Z-Wave migration handler."""
    migration_handler = LegacyZWaveMigration(hass)
    await migration_handler.load_data()
    return migration_handler


class LegacyZWaveMigration:
    """Handle the migration from zwave to ozw and zwave_js."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up migration instance."""
        self._hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, dict[str, ZWaveMigrationData]] = {}

    async def load_data(self) -> None:
        """Load Z-Wave migration data."""
        stored = cast(dict, await self._store.async_load())
        if stored:
            self._data = stored

    @callback
    def save_data(
        self, config_entry_id: str, entity_id: str, data: ZWaveMigrationData
    ) -> None:
        """Save Z-Wave migration data."""
        if config_entry_id not in self._data:
            self._data[config_entry_id] = {}
        self._data[config_entry_id][entity_id] = data
        self._store.async_delay_save(self._data_to_save, STORAGE_WRITE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, ZWaveMigrationData]]:
        """Return data to save."""
        return self._data

    @callback
    def add_entity_value(
        self,
        entity_id: str,
        entity_values: ZWaveDeviceEntityValues,
    ) -> None:
        """Add info for one entity and Z-Wave value."""
        ent_reg = async_get_entity_registry(self._hass)
        dev_reg = async_get_device_registry(self._hass)

        node = entity_values.primary.node
        entity_entry = ent_reg.async_get(entity_id)
        assert entity_entry
        device_identifier, _ = node_device_id_and_name(
            node, entity_values.primary.instance
        )
        device_entry = dev_reg.async_get_device({device_identifier}, set())
        assert device_entry

        # Normalize unit of measurement.
        if unit := entity_entry.unit_of_measurement:
            unit = unit.lower()
        if unit == "":
            unit = None

        data: ZWaveMigrationData = {
            "node_id": node.node_id,
            "node_instance": entity_values.primary.instance,
            "command_class": entity_values.primary.command_class,
            "command_class_label": entity_values.primary.label,
            "value_index": entity_values.primary.index,
            "device_id": device_entry.id,
            "domain": entity_entry.domain,
            "entity_id": entity_id,
            "unique_id": entity_entry.unique_id,
            "unit_of_measurement": unit,
        }

        self.save_data(entity_entry.config_entry_id, entity_id, data)

    async def get_data(
        self, config_entry: ConfigEntry
    ) -> dict[str, ZWaveMigrationData]:
        """Return Z-Wave migration data."""
        await self.load_data()
        data = self._data.get(config_entry.entry_id)
        return data or {}
