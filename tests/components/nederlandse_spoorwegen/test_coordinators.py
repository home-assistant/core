"""Tests for Nederlandse Spoorwegen coordinators manager."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.components.nederlandse_spoorwegen.coordinators import (
    NSCoordinatorsManager,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import (
    API_KEY,
    SUBENTRY_ID_1,
    SUBENTRY_ID_2,
    TEST_ROUTE_TITLE_1,
    TEST_ROUTE_TITLE_2,
)

from tests.common import MockConfigEntry


class TestNSCoordinatorsManager:
    """Test the NS Coordinators Manager."""

    def test_manager_initialization(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ):
        """Test manager initialization."""
        manager = NSCoordinatorsManager(hass, mock_config_entry)

        assert manager.hass == hass
        assert manager.config_entry == mock_config_entry
        assert manager._coordinators == {}
        assert manager.coordinator_count == 0

    async def test_async_setup_no_routes(self, manager):
        """Test setup with no routes."""
        # Create a manager with empty config entry
        empty_config = MockConfigEntry(
            title="Nederlandse Spoorwegen",
            data={CONF_API_KEY: API_KEY},
            domain=DOMAIN,
            subentries_data=[],
        )
        empty_manager = NSCoordinatorsManager(manager.hass, empty_config)

        await empty_manager.async_setup()

        assert empty_manager.coordinator_count == 0
        assert empty_manager.get_route_ids() == []

    async def test_async_setup_with_routes(
        self, hass: HomeAssistant, mock_config_entry_with_multiple_routes
    ):
        """Test setup with multiple routes."""
        manager = NSCoordinatorsManager(hass, mock_config_entry_with_multiple_routes)

        with patch.object(
            manager, "async_add_coordinator", new_callable=AsyncMock
        ) as mock_add:
            await manager.async_setup()

            assert mock_add.call_count == 2
            mock_add.assert_any_call(
                SUBENTRY_ID_1, {"name": TEST_ROUTE_TITLE_1, "from": "Ams", "to": "Rot"}
            )
            mock_add.assert_any_call(
                SUBENTRY_ID_2, {"name": TEST_ROUTE_TITLE_2, "from": "Hag", "to": "Utr"}
            )

    async def test_async_add_coordinator_success(self, manager, mock_nsapi):
        """Test successfully adding a coordinator."""
        route_data = {
            "name": "Test Route",
            "from": "Ams",
            "to": "Rot",
        }

        with patch(
            "homeassistant.components.nederlandse_spoorwegen.coordinators.NSDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            result = await manager.async_add_coordinator("test_route", route_data)

            assert result == mock_coordinator
            assert manager.has_coordinator("test_route")
            assert manager.coordinator_count == 1
            assert "test_route" in manager.get_route_ids()
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()

    async def test_async_remove_coordinator_success(self, manager):
        """Test successfully removing a coordinator."""
        route_data = {"name": "Test Route", "from": "Ams", "to": "Rot"}

        # Add a coordinator first
        with patch(
            "homeassistant.components.nederlandse_spoorwegen.coordinators.NSDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator
            await manager.async_add_coordinator("test_route", route_data)

            # Remove it
            await manager.async_remove_coordinator("test_route")

            assert not manager.has_coordinator("test_route")
            assert manager.coordinator_count == 0

    def test_get_coordinator(self, manager):
        """Test getting a coordinator."""
        # Non-existent coordinator
        result = manager.get_coordinator("non_existent")
        assert result is None

    def test_coordinator_properties(self, manager):
        """Test coordinator properties methods."""
        assert manager.coordinator_count == 0
        assert manager.get_route_ids() == []
        assert not manager.has_coordinator("test")
        assert manager.get_coordinator("test") is None
        assert manager.get_all_coordinators() == {}

    async def test_async_unload_all(self, manager):
        """Test unloading all coordinators."""
        route_data = {"name": "Test Route", "from": "Ams", "to": "Rot"}

        # Add a coordinator first
        with patch(
            "homeassistant.components.nederlandse_spoorwegen.coordinators.NSDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator
            await manager.async_add_coordinator("test_route", route_data)

            assert manager.coordinator_count == 1

            await manager.async_unload_all()

            assert manager.coordinator_count == 0
            assert manager.get_route_ids() == []
