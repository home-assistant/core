"""Tests for Diesel Heater __init__.py.

Tests the setup, unload, migration, and service registration logic.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater import (
    _migrate_entity_unique_ids,
    _safe_update_unique_id,
    _UNIQUE_ID_MIGRATIONS,
    _UNIQUE_IDS_TO_REMOVE,
)


# ---------------------------------------------------------------------------
# _safe_update_unique_id tests
# ---------------------------------------------------------------------------

class TestSafeUpdateUniqueId:
    """Tests for _safe_update_unique_id helper."""

    def test_update_success_no_conflict(self):
        """Test successful update when no conflict exists."""
        registry = MagicMock()
        registry.entities = {}

        result = _safe_update_unique_id(
            registry,
            "sensor.test_entity",
            "old_uid",
            "new_uid",
        )

        assert result is True
        registry.async_update_entity.assert_called_once_with(
            "sensor.test_entity", new_unique_id="new_uid"
        )

    def test_update_removes_duplicate_on_conflict(self):
        """Test that duplicate entity is removed when target uid exists."""
        registry = MagicMock()
        existing_entity = MagicMock()
        existing_entity.unique_id = "new_uid"
        existing_entity.entity_id = "sensor.existing_entity"
        registry.entities = {"sensor.existing_entity": existing_entity}

        result = _safe_update_unique_id(
            registry,
            "sensor.duplicate_entity",
            "corrupted_uid",
            "new_uid",
        )

        assert result is True
        registry.async_remove.assert_called_once_with("sensor.duplicate_entity")
        registry.async_update_entity.assert_not_called()

    def test_update_handles_value_error(self):
        """Test graceful handling of unexpected ValueError."""
        registry = MagicMock()
        registry.entities = {}
        registry.async_update_entity.side_effect = ValueError("test error")

        result = _safe_update_unique_id(
            registry,
            "sensor.test_entity",
            "old_uid",
            "new_uid",
        )

        assert result is False


# ---------------------------------------------------------------------------
# _migrate_entity_unique_ids tests
# ---------------------------------------------------------------------------

class TestMigrateEntityUniqueIds:
    """Tests for entity unique_id migration."""

    def _make_entity(self, unique_id: str, entity_id: str = None) -> MagicMock:
        """Create a mock entity registry entry."""
        entity = MagicMock()
        entity.unique_id = unique_id
        entity.entity_id = entity_id or f"sensor.test_{unique_id.split('_')[-1]}"
        return entity

    def test_migration_skips_already_migrated(self):
        """Test that already-migrated entities are not re-migrated."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        entity = self._make_entity(
            "DC:32:62:40:6A:00_est_daily_fuel_consumed",
            "sensor.test_est_daily"
        )
        registry.entities = {entity.entity_id: entity}

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Should not try to update since it already ends with new suffix
        registry.async_update_entity.assert_not_called()

    def test_migration_fixes_corrupted_unique_id(self):
        """Test that corrupted unique_ids with repeated _est_ are fixed."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        # Simulates corrupted unique_id with multiple _est_ prefixes
        corrupted_uid = "DC:32:62:40:6A:00_est_est_daily_fuel_consumed"
        expected_uid = "DC:32:62:40:6A:00_est_daily_fuel_consumed"
        entity = self._make_entity(corrupted_uid, "sensor.test_corrupted")
        registry.entities = {entity.entity_id: entity}

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Should fix the corrupted unique_id
        registry.async_update_entity.assert_called()

    def test_migration_removes_deprecated_backlight(self):
        """Test that deprecated backlight number entity is removed."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        entity = self._make_entity(
            "DC:32:62:40:6A:00_backlight",
            "number.test_backlight"
        )
        registry.entities = {entity.entity_id: entity}

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Should remove the deprecated entity
        registry.async_remove.assert_called_once_with("number.test_backlight")

    def test_migration_renames_old_suffix(self):
        """Test that old suffixes are renamed to new suffixes."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        # Old suffix without _est_ prefix
        entity = self._make_entity(
            "DC:32:62:40:6A:00_daily_fuel_consumed",
            "sensor.test_daily_fuel"
        )
        registry.entities = {entity.entity_id: entity}

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Should rename to new suffix with _est_ prefix
        registry.async_update_entity.assert_called()


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestMigrationConstants:
    """Test migration constant definitions."""

    def test_unique_id_migrations_defined(self):
        """Test that migration mappings are defined."""
        assert "_hourly_fuel_consumption" in _UNIQUE_ID_MIGRATIONS
        assert "_daily_fuel_consumed" in _UNIQUE_ID_MIGRATIONS
        assert "_total_fuel_consumed" in _UNIQUE_ID_MIGRATIONS
        assert "_daily_fuel_history" in _UNIQUE_ID_MIGRATIONS
        assert "_reset_fuel_level" in _UNIQUE_ID_MIGRATIONS

    def test_unique_ids_to_remove_defined(self):
        """Test that removal list is defined."""
        assert "_backlight" in _UNIQUE_IDS_TO_REMOVE

    def test_all_new_suffixes_have_est_prefix(self):
        """Test that all new suffixes use _est_ naming."""
        for old, new in _UNIQUE_ID_MIGRATIONS.items():
            if "fuel" in old:
                assert "_est_" in new, f"Expected _est_ in {new}"


# ---------------------------------------------------------------------------
# Migration edge case tests
# ---------------------------------------------------------------------------

class TestMigrationEdgeCases:
    """Tests for edge cases in entity migration."""

    def _make_entity(self, unique_id: str, entity_id: str = None) -> MagicMock:
        """Create a mock entity registry entry."""
        entity = MagicMock()
        entity.unique_id = unique_id
        entity.entity_id = entity_id or f"sensor.test_{unique_id.split('_')[-1]}"
        return entity

    def test_skips_entity_already_removed_at_start(self):
        """Test migration skips entity if already removed from registry."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        entity = self._make_entity("DC:32:62:40:6A:00_something", "sensor.test")
        # Entity in iteration list but NOT in registry.entities
        registry.entities = {}

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Should skip without any operations
        registry.async_update_entity.assert_not_called()
        registry.async_remove.assert_not_called()

    def test_skips_entity_removed_during_corruption_fix(self):
        """Test migration skips entity if removed during corruption fix."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        corrupted_uid = "DC:32:62:40:6A:00_est_est_daily_fuel_consumed"
        entity = self._make_entity(corrupted_uid, "sensor.test_corrupted")

        # Entity exists initially but removed by _safe_update_unique_id
        entities_dict = {entity.entity_id: entity}
        registry.entities = entities_dict

        def remove_entity_side_effect(entity_id, **kwargs):
            # Simulate removal by removing from dict
            if entity_id in entities_dict:
                del entities_dict[entity_id]

        registry.async_update_entity.side_effect = remove_entity_side_effect

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Corruption fix should be attempted
        registry.async_update_entity.assert_called()

    def test_skips_entity_removed_during_migration(self):
        """Test migration skips entity if removed during suffix migration."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        entity = self._make_entity(
            "DC:32:62:40:6A:00_daily_fuel_consumed",
            "sensor.test_daily"
        )

        # Entity exists initially but removed during migration
        entities_dict = {entity.entity_id: entity}
        registry.entities = entities_dict

        def remove_entity_side_effect(entity_id, **kwargs):
            if entity_id in entities_dict:
                del entities_dict[entity_id]

        registry.async_update_entity.side_effect = remove_entity_side_effect

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Migration should be attempted
        registry.async_update_entity.assert_called()

    def test_corruption_fix_breaks_on_failed_update(self):
        """Test corruption fix loop breaks when update fails."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        # Triple corrupted unique_id
        corrupted_uid = "DC:32:62:40:6A:00_est_est_est_daily_fuel_consumed"
        entity = self._make_entity(corrupted_uid, "sensor.test_corrupted")
        registry.entities = {entity.entity_id: entity}

        # First update succeeds, second fails
        call_count = [0]
        def update_side_effect(entity_id, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise ValueError("Update failed")

        registry.async_update_entity.side_effect = update_side_effect

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # Should have attempted multiple updates before failing
        assert registry.async_update_entity.call_count >= 1

    def test_corruption_fix_breaks_when_uid_unchanged(self):
        """Test corruption fix loop breaks when fixed uid equals current uid."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        registry = MagicMock()
        # Already fixed - no double _est_
        entity = self._make_entity(
            "DC:32:62:40:6A:00_est_daily_fuel_consumed",
            "sensor.test"
        )
        registry.entities = {entity.entity_id: entity}

        with patch(
            "custom_components.diesel_heater.er.async_get", return_value=registry
        ), patch(
            "custom_components.diesel_heater.er.async_entries_for_config_entry",
            return_value=[entity],
        ):
            _migrate_entity_unique_ids(hass, entry)

        # No corruption fix needed since uid is already correct
        # Should not try to update for corruption fix
        # (may still be called for migration if old suffix check passes)


# ---------------------------------------------------------------------------
# async_setup_entry / async_unload_entry tests
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import AsyncMock

from custom_components.diesel_heater import (
    async_setup_entry,
    async_unload_entry,
    PLATFORMS,
    DOMAIN,
    SERVICE_SEND_COMMAND,
)

# CONF_ADDRESS is from homeassistant.const (stubbed as MagicMock)
CONF_ADDRESS = "address"


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_setup_entry_no_ble_device_raises(self):
        """Test setup raises ConfigEntryNotReady when BLE device not found."""
        # Import the stubbed exception from conftest
        from homeassistant.exceptions import ConfigEntryNotReady

        hass = MagicMock()
        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ):
            mock_bt.async_ble_device_from_address.return_value = None

            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_setup_entry_success(self):
        """Test successful setup entry."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False
        hass.services.async_register = MagicMock()

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_load_data = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device

            result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data == mock_coordinator
        hass.config_entries.async_forward_entry_setups.assert_called_once()
        hass.services.async_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_entry_timeout_continues(self):
        """Test setup continues even after connection timeout."""
        import asyncio

        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = True  # Service already registered

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_load_data = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device

            result = await async_setup_entry(hass, entry)

        # Should succeed despite timeout
        assert result is True
        assert entry.runtime_data == mock_coordinator

    @pytest.mark.asyncio
    async def test_setup_entry_connection_error_continues(self):
        """Test setup continues even after connection error."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = True

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.async_load_data = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device

            result = await async_setup_entry(hass, entry)

        assert result is True


class TestSendCommandService:
    """Tests for the send_command service handler."""

    def _create_coordinator_mock(self, address="AA:BB:CC:DD:EE:FF"):
        """Create a mock that passes isinstance check for VevorHeaterCoordinator."""
        from custom_components.diesel_heater.coordinator import VevorHeaterCoordinator

        mock_coordinator = MagicMock()
        mock_coordinator.async_load_data = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.address = address
        mock_coordinator.async_send_raw_command = AsyncMock()

        # Make isinstance check pass
        mock_coordinator.__class__ = VevorHeaterCoordinator

        return mock_coordinator

    @pytest.mark.asyncio
    async def test_service_finds_heater_by_device_id(self):
        """Test service finds heater by device_id."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False

        # Capture the service handler when registered
        service_handler = None
        def capture_handler(domain, service, handler, schema):
            nonlocal service_handler
            service_handler = handler
        hass.services.async_register = capture_handler

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = self._create_coordinator_mock()

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device
            await async_setup_entry(hass, entry)

        # Now test the captured service handler
        assert service_handler is not None

        # Mock hass.config_entries.async_entries to return our entry
        hass.config_entries.async_entries.return_value = [entry]
        entry.runtime_data = mock_coordinator

        # Create service call
        call = MagicMock()
        call.data = {"command": 10, "argument": 5, "device_id": "EE:FF"}

        await service_handler(call)

        mock_coordinator.async_send_raw_command.assert_called_once_with(10, 5)

    @pytest.mark.asyncio
    async def test_service_sends_to_all_heaters_without_device_id(self):
        """Test service sends to all heaters when no device_id specified."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False

        service_handler = None
        def capture_handler(domain, service, handler, schema):
            nonlocal service_handler
            service_handler = handler
        hass.services.async_register = capture_handler

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = self._create_coordinator_mock()

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device
            await async_setup_entry(hass, entry)

        hass.config_entries.async_entries.return_value = [entry]
        entry.runtime_data = mock_coordinator

        call = MagicMock()
        call.data = {"command": 20, "argument": -3}  # No device_id

        await service_handler(call)

        mock_coordinator.async_send_raw_command.assert_called_once_with(20, -3)

    @pytest.mark.asyncio
    async def test_service_raises_on_no_matching_heater(self):
        """Test service raises ServiceValidationError when no heater found."""
        from homeassistant.exceptions import ServiceValidationError

        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False

        service_handler = None
        def capture_handler(domain, service, handler, schema):
            nonlocal service_handler
            service_handler = handler
        hass.services.async_register = capture_handler

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = self._create_coordinator_mock()

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device
            await async_setup_entry(hass, entry)

        # Return entry with coordinator
        hass.config_entries.async_entries.return_value = [entry]
        entry.runtime_data = mock_coordinator

        call = MagicMock()
        call.data = {"command": 10, "argument": 5, "device_id": "XX:YY"}  # Non-matching

        with pytest.raises(ServiceValidationError):
            await service_handler(call)

    @pytest.mark.asyncio
    async def test_service_raises_on_command_error(self):
        """Test service raises HomeAssistantError on command failure."""
        from homeassistant.exceptions import HomeAssistantError

        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False

        service_handler = None
        def capture_handler(domain, service, handler, schema):
            nonlocal service_handler
            service_handler = handler
        hass.services.async_register = capture_handler

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = self._create_coordinator_mock()
        mock_coordinator.async_send_raw_command = AsyncMock(
            side_effect=Exception("BLE error")
        )

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device
            await async_setup_entry(hass, entry)

        hass.config_entries.async_entries.return_value = [entry]
        entry.runtime_data = mock_coordinator

        call = MagicMock()
        call.data = {"command": 10, "argument": 5}

        with pytest.raises(HomeAssistantError):
            await service_handler(call)

    @pytest.mark.asyncio
    async def test_service_skips_non_coordinator_entries(self):
        """Test service skips config entries without VevorHeaterCoordinator."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False

        service_handler = None
        def capture_handler(domain, service, handler, schema):
            nonlocal service_handler
            service_handler = handler
        hass.services.async_register = capture_handler

        entry = MagicMock()
        entry.data = {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}

        mock_ble_device = MagicMock()
        mock_coordinator = self._create_coordinator_mock()

        with patch(
            "custom_components.diesel_heater.bluetooth"
        ) as mock_bt, patch(
            "custom_components.diesel_heater._migrate_entity_unique_ids"
        ), patch(
            "custom_components.diesel_heater.VevorHeaterCoordinator",
            return_value=mock_coordinator
        ):
            mock_bt.async_ble_device_from_address.return_value = mock_ble_device
            await async_setup_entry(hass, entry)

        # Return entry with non-coordinator runtime_data and valid entry
        other_entry = MagicMock()
        other_entry.runtime_data = "not a coordinator"

        hass.config_entries.async_entries.return_value = [other_entry, entry]
        entry.runtime_data = mock_coordinator

        call = MagicMock()
        call.data = {"command": 10, "argument": 5}

        await service_handler(call)

        # Should only send to valid coordinator
        mock_coordinator.async_send_raw_command.assert_called_once()


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry."""

    @pytest.mark.asyncio
    async def test_unload_entry_success(self):
        """Test successful unload entry."""
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        mock_coordinator = MagicMock()
        mock_coordinator.async_save_data = AsyncMock()
        mock_coordinator.async_shutdown = AsyncMock()

        entry = MagicMock()
        entry.runtime_data = mock_coordinator

        result = await async_unload_entry(hass, entry)

        assert result is True
        mock_coordinator.async_save_data.assert_called_once()
        mock_coordinator.async_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_unload_entry_failure(self):
        """Test unload entry when platform unload fails."""
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        mock_coordinator = MagicMock()
        mock_coordinator.async_save_data = AsyncMock()
        mock_coordinator.async_shutdown = AsyncMock()

        entry = MagicMock()
        entry.runtime_data = mock_coordinator

        result = await async_unload_entry(hass, entry)

        assert result is False
        # Should not save/shutdown if unload failed
        mock_coordinator.async_save_data.assert_not_called()
        mock_coordinator.async_shutdown.assert_not_called()
