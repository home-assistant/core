"""Test migration of legacy routes from configuration to subentries.

This module tests the migration functionality that automatically
imports legacy routes from config entry data (from YAML configuration)
into the new subentry format.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.nederlandse_spoorwegen import (
    CONF_FROM,
    CONF_NAME,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_migrate_legacy_routes_from_data(hass: HomeAssistant) -> None:
    """Test migration of legacy routes from config entry data (YAML config)."""
    with (
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper"
        ) as mock_api_wrapper_class,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper.convert_station_name_to_code"
        ) as mock_convert,
    ):
        # Mock convert_station_name_to_code to return uppercase strings
        mock_convert.side_effect = (
            lambda code, stations=None: str(code).upper() if code else ""
        )

        # Mock stations with required station codes
        mock_station_asd = type(
            "Station", (), {"code": "ASD", "name": "Amsterdam Centraal"}
        )()
        mock_station_rtd = type(
            "Station", (), {"code": "RTD", "name": "Rotterdam Centraal"}
        )()
        mock_station_gn = type("Station", (), {"code": "GN", "name": "Groningen"})()
        mock_station_mt = type("Station", (), {"code": "MT", "name": "Maastricht"})()
        mock_station_zl = type("Station", (), {"code": "ZL", "name": "Zwolle"})()

        # Set up the mock API wrapper
        mock_api_wrapper = MagicMock()
        # Make async methods async
        mock_api_wrapper.get_stations = AsyncMock(
            return_value=[
                mock_station_asd,
                mock_station_rtd,
                mock_station_gn,
                mock_station_mt,
                mock_station_zl,
            ]
        )
        mock_api_wrapper.get_trips = AsyncMock(return_value=[])
        mock_api_wrapper.validate_api_key = AsyncMock(return_value=None)
        # Mock the get_station_codes as a regular method (not async)
        mock_api_wrapper.get_station_codes = MagicMock(
            return_value={"ASD", "RTD", "GN", "MT", "ZL"}
        )
        # Mock the convert_station_name_to_code method as regular method
        mock_api_wrapper.convert_station_name_to_code = MagicMock(
            side_effect=lambda code, stations=None: str(code).upper() if code else ""
        )
        mock_api_wrapper_class.return_value = mock_api_wrapper

        # Create config entry with legacy routes in data (from YAML config)
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "api_key": "test_key",
                "routes": [
                    {
                        CONF_NAME: "Legacy Route 1",
                        CONF_FROM: "Asd",
                        CONF_TO: "Rtd",
                    },
                    {
                        CONF_NAME: "Legacy Route 2",
                        CONF_FROM: "Gn",
                        CONF_TO: "Mt",
                        CONF_VIA: "Zl",
                        CONF_TIME: "08:06:00",
                    },
                ],
            },
        )
        config_entry.add_to_hass(hass)

        # Setup should succeed and migrate routes
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED

        # Check that routes were migrated as subentries
        assert len(config_entry.subentries) == 2

        # Check first route subentry
        subentry_1 = next(
            subentry
            for subentry in config_entry.subentries.values()
            if subentry.title == "Legacy Route 1"
        )
        assert subentry_1.data[CONF_NAME] == "Legacy Route 1"
        assert subentry_1.data[CONF_FROM] == "ASD"
        assert subentry_1.data[CONF_TO] == "RTD"
        assert CONF_VIA not in subentry_1.data

        # Check second route subentry
        subentry_2 = next(
            subentry
            for subentry in config_entry.subentries.values()
            if subentry.title == "Legacy Route 2"
        )
        assert subentry_2.data[CONF_NAME] == "Legacy Route 2"
        assert subentry_2.data[CONF_FROM] == "GN"
        assert subentry_2.data[CONF_TO] == "MT"
        assert subentry_2.data[CONF_VIA] == "ZL"
        assert subentry_2.data[CONF_TIME] == "08:06:00"

        # Check migration marker was set
        assert config_entry.options.get("routes_migrated") is True

        # Check legacy routes were removed from data
        assert "routes" not in config_entry.data

        # Unload entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_no_migration_when_already_migrated(hass: HomeAssistant) -> None:
    """Test that migration is skipped when already done."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper"
    ) as mock_api_wrapper_class:
        # Mock stations with required station codes
        mock_station_asd = type(
            "Station", (), {"code": "ASD", "name": "Amsterdam Centraal"}
        )()
        mock_station_rtd = type(
            "Station", (), {"code": "RTD", "name": "Rotterdam Centraal"}
        )()

        # Set up the mock API wrapper
        mock_api_wrapper = AsyncMock()
        mock_api_wrapper.get_stations.return_value = [
            mock_station_asd,
            mock_station_rtd,
        ]
        # Mock the get_station_codes as a regular method (not async)
        mock_api_wrapper.get_station_codes = MagicMock(
            return_value={"ASD", "RTD", "GN", "MT", "ZL"}
        )
        mock_api_wrapper.get_trips.return_value = []
        mock_api_wrapper.validate_api_key.return_value = None
        mock_api_wrapper_class.return_value = mock_api_wrapper

        # Create config entry WITHOUT legacy routes - migration already done
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"api_key": "test_key"},  # No routes in data
            options={"routes_migrated": True},  # Migration marker set
        )
        config_entry.add_to_hass(hass)

        # Setup should succeed but not migrate
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED

        # Check that no subentries were created
        assert len(config_entry.subentries) == 0

        # Check migration marker is still set
        assert config_entry.options.get("routes_migrated") is True

        # No routes should be present since migration was already done
        assert "routes" not in config_entry.data

        # Unload entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_no_migration_when_no_routes(hass: HomeAssistant) -> None:
    """Test that migration completes gracefully when no routes exist."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper"
    ) as mock_api_wrapper_class:
        # Set up the mock API wrapper
        mock_api_wrapper = AsyncMock()
        # Provide stations to prevent coordinator failure
        mock_station_asd = type(
            "Station", (), {"code": "ASD", "name": "Amsterdam Centraal"}
        )()
        mock_station_rtd = type(
            "Station", (), {"code": "RTD", "name": "Rotterdam Centraal"}
        )()
        mock_api_wrapper.get_stations.return_value = [
            mock_station_asd,
            mock_station_rtd,
        ]
        # Mock the get_station_codes as a regular method (not async)
        mock_api_wrapper.get_station_codes = MagicMock(
            return_value={"ASD", "RTD", "GN", "MT", "ZL"}
        )
        mock_api_wrapper.get_trips.return_value = []
        mock_api_wrapper.validate_api_key.return_value = None
        mock_api_wrapper_class.return_value = mock_api_wrapper

        # Create config entry without routes
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"api_key": "test_key"},
        )
        config_entry.add_to_hass(hass)

        # Setup should succeed
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED

        # Check that no subentries were created
        assert len(config_entry.subentries) == 0

        # Check migration marker was still set (even with no routes)
        assert config_entry.options.get("routes_migrated") is True

        # Unload entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_migration_error_handling(hass: HomeAssistant) -> None:
    """Test migration handles malformed routes gracefully."""
    with (
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper"
        ) as mock_api_wrapper_class,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper.convert_station_name_to_code",
            side_effect=lambda code, stations=None: str(code).upper() if code else "",
        ),
    ):
        # Mock stations with required station codes
        mock_station_asd = type(
            "Station", (), {"code": "ASD", "name": "Amsterdam Centraal"}
        )()
        mock_station_rtd = type(
            "Station", (), {"code": "RTD", "name": "Rotterdam Centraal"}
        )()
        mock_station_hrl = type(
            "Station", (), {"code": "HRL", "name": "Harlingen Haven"}
        )()
        mock_station_ut = type(
            "Station", (), {"code": "UT", "name": "Utrecht Centraal"}
        )()
        mock_station_ams = type(
            "Station", (), {"code": "AMS", "name": "Amsterdam Zuid"}
        )()

        # Set up the mock API wrapper
        mock_api_wrapper = MagicMock()
        # Make async methods async
        mock_api_wrapper.get_stations = AsyncMock(
            return_value=[
                mock_station_asd,
                mock_station_rtd,
                mock_station_hrl,
                mock_station_ut,
                mock_station_ams,
            ]
        )
        mock_api_wrapper.get_trips = AsyncMock(return_value=[])
        mock_api_wrapper.validate_api_key = AsyncMock(return_value=None)
        # Mock the get_station_codes as a regular method (not async)
        mock_api_wrapper.get_station_codes = MagicMock(
            return_value={"ASD", "RTD", "GN", "MT", "ZL"}
        )
        # Mock the convert_station_name_to_code method as regular method
        mock_api_wrapper.convert_station_name_to_code = MagicMock(
            side_effect=lambda code, stations=None: str(code).upper() if code else ""
        )
        mock_api_wrapper_class.return_value = mock_api_wrapper

        # Create config entry with mix of valid and invalid routes
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "api_key": "test_key",
                "routes": [
                    {
                        CONF_NAME: "Valid Route",
                        CONF_FROM: "Asd",
                        CONF_TO: "Rtd",
                    },
                    {
                        # Missing CONF_TO
                        CONF_NAME: "Invalid Route 1",
                        CONF_FROM: "Gn",
                    },
                    {
                        # Missing CONF_NAME
                        CONF_FROM: "Zl",
                        CONF_TO: "Mt",
                    },
                    {
                        CONF_NAME: "Another Valid Route",
                        CONF_FROM: "Hrl",
                        CONF_TO: "Ut",
                        CONF_VIA: "Ams",
                    },
                ],
            },
        )
        config_entry.add_to_hass(hass)

        # Setup should succeed despite invalid routes
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED

        # Check that only valid routes were migrated
        assert len(config_entry.subentries) == 2

        # Check migration marker was set
        assert config_entry.options.get("routes_migrated") is True

        # Check legacy routes were removed from data
        assert "routes" not in config_entry.data

        # Unload entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_migration_unique_id_generation(hass: HomeAssistant) -> None:
    """Test unique ID generation for migrated routes."""
    with (
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper"
        ) as mock_api_wrapper_class,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper.convert_station_name_to_code"
        ) as mock_convert,
    ):
        # Mock convert_station_name_to_code to return uppercase strings
        mock_convert.side_effect = (
            lambda code, stations=None: str(code).upper() if code else ""
        )

        # Mock stations with required station codes
        mock_station_asd = type(
            "Station", (), {"code": "ASD", "name": "Amsterdam Centraal"}
        )()
        mock_station_rtd = type(
            "Station", (), {"code": "RTD", "name": "Rotterdam Centraal"}
        )()
        mock_station_gn = type("Station", (), {"code": "GN", "name": "Groningen"})()
        mock_station_mt = type("Station", (), {"code": "MT", "name": "Maastricht"})()
        mock_station_zl = type("Station", (), {"code": "ZL", "name": "Zwolle"})()

        # Set up the mock API wrapper
        mock_api_wrapper = MagicMock()
        # Make async methods async
        mock_api_wrapper.get_stations = AsyncMock(
            return_value=[
                mock_station_asd,
                mock_station_rtd,
                mock_station_gn,
                mock_station_mt,
                mock_station_zl,
            ]
        )
        mock_api_wrapper.get_trips = AsyncMock(return_value=[])
        mock_api_wrapper.validate_api_key = AsyncMock(return_value=None)
        # Mock the get_station_codes as a regular method (not async)
        mock_api_wrapper.get_station_codes = MagicMock(
            return_value={"ASD", "RTD", "GN", "MT", "ZL"}
        )
        # Mock the convert_station_name_to_code method as regular method
        mock_api_wrapper.convert_station_name_to_code = MagicMock(
            side_effect=lambda code, stations=None: str(code).upper() if code else ""
        )
        mock_api_wrapper_class.return_value = mock_api_wrapper

        # Create config entry with routes that test unique_id generation
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "api_key": "test_key",
                "routes": [
                    {
                        CONF_NAME: "Simple Route",
                        CONF_FROM: "asd",  # lowercase to test conversion
                        CONF_TO: "rtd",
                    },
                    {
                        CONF_NAME: "Route with Via",
                        CONF_FROM: "GN",  # mixed case
                        CONF_TO: "mt",
                        CONF_VIA: "Zl",
                    },
                ],
            },
        )
        config_entry.add_to_hass(hass)

        # Setup should succeed
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED

        # Check that routes were migrated with correct unique_ids
        assert len(config_entry.subentries) == 2

        # Find the simple route and check its unique_id
        simple_route = next(
            subentry
            for subentry in config_entry.subentries.values()
            if subentry.title == "Simple Route"
        )
        assert simple_route.unique_id == "ASD_RTD"

        # Find the route with via and check its unique_id
        via_route = next(
            subentry
            for subentry in config_entry.subentries.values()
            if subentry.title == "Route with Via"
        )
        assert via_route.unique_id == "GN_MT_ZL"

        # Unload entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)
