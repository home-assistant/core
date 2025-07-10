"""Test service functionality for the Nederlandse Spoorwegen integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nederlandse_spoorwegen import DOMAIN
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_nsapi():
    """Mock NSAPI client."""
    nsapi = MagicMock()
    nsapi.get_stations.return_value = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    nsapi.get_trips.return_value = []
    return nsapi


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_id",
        data={CONF_API_KEY: "test_api_key"},
        options={"routes": []},
    )


@pytest.fixture
def mock_coordinator(mock_config_entry, mock_nsapi):
    """Mock coordinator."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()

    coordinator = NSDataUpdateCoordinator(hass, mock_nsapi, mock_config_entry)
    coordinator.data = {
        "routes": {},
        "stations": [MagicMock(code="AMS"), MagicMock(code="UTR")],
    }
    return coordinator


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_coordinator: MagicMock
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.runtime_data = {"coordinator": mock_coordinator}

    # Setup component to register services
    await async_setup_component(hass, DOMAIN, {})

    return mock_config_entry


async def test_add_route_service(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test the add_route service."""
    # Create a fully mocked config entry with the required attributes
    mock_entry = MagicMock()
    mock_entry.runtime_data = {
        "coordinator": init_integration.runtime_data["coordinator"]
    }
    mock_state = MagicMock()
    mock_state.name = "LOADED"
    mock_entry.state = mock_state

    # Patch the config entries lookup to return our mock entry
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_entries"
    ) as mock_entries:
        mock_entries.return_value = [mock_entry]

        with patch.object(
            init_integration.runtime_data["coordinator"], "async_add_route"
        ) as mock_add:
            await hass.services.async_call(
                DOMAIN,
                "add_route",
                {
                    "name": "Test Route",
                    "from": "AMS",
                    "to": "UTR",
                    "via": "RTD",
                },
                blocking=True,
            )

            mock_add.assert_called_once_with(
                {
                    "name": "Test Route",
                    "from": "AMS",
                    "to": "UTR",
                    "via": "RTD",
                }
            )


async def test_remove_route_service(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test the remove_route service."""
    # Create a fully mocked config entry with the required attributes
    mock_entry = MagicMock()
    mock_entry.runtime_data = {
        "coordinator": init_integration.runtime_data["coordinator"]
    }
    mock_state = MagicMock()
    mock_state.name = "LOADED"
    mock_entry.state = mock_state

    # Patch the config entries lookup to return our mock entry
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_entries"
    ) as mock_entries:
        mock_entries.return_value = [mock_entry]

        with patch.object(
            init_integration.runtime_data["coordinator"], "async_remove_route"
        ) as mock_remove:
            await hass.services.async_call(
                DOMAIN,
                "remove_route",
                {"name": "Test Route"},
                blocking=True,
            )

            mock_remove.assert_called_once_with("Test Route")


async def test_service_no_integration(hass: HomeAssistant) -> None:
    """Test service calls when no integration is configured."""
    # Set up only the component (services) without any config entries
    await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(
        ServiceValidationError, match="No Nederlandse Spoorwegen integration found"
    ):
        await hass.services.async_call(
            DOMAIN,
            "add_route",
            {
                "name": "Test Route",
                "from": "AMS",
                "to": "UTR",
            },
            blocking=True,
        )


async def test_service_integration_not_loaded(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test service calls when integration is not loaded."""
    # Setup component but with unloaded config entry
    await async_setup_component(hass, DOMAIN, {})

    # Create a fully mocked config entry with NOT_LOADED state
    mock_entry = MagicMock()
    mock_state = MagicMock()
    mock_state.name = "NOT_LOADED"
    mock_entry.state = mock_state

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_entries"
    ) as mock_entries:
        mock_entries.return_value = [mock_entry]

        with pytest.raises(
            ServiceValidationError,
            match="Nederlandse Spoorwegen integration not loaded",
        ):
            await hass.services.async_call(
                DOMAIN,
                "add_route",
                {
                    "name": "Test Route",
                    "from": "AMS",
                    "to": "UTR",
                },
                blocking=True,
            )


async def test_add_route_service_with_via_and_time(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test the add_route service with optional via and time parameters."""
    # Create a fully mocked config entry with the required attributes
    mock_entry = MagicMock()
    mock_entry.runtime_data = {
        "coordinator": init_integration.runtime_data["coordinator"]
    }
    mock_state = MagicMock()
    mock_state.name = "LOADED"
    mock_entry.state = mock_state

    # Patch the config entries lookup to return our mock entry
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_entries"
    ) as mock_entries:
        mock_entries.return_value = [mock_entry]

        with patch.object(
            init_integration.runtime_data["coordinator"], "async_add_route"
        ) as mock_add:
            await hass.services.async_call(
                DOMAIN,
                "add_route",
                {
                    "name": "Complex Route",
                    "from": "ams",
                    "to": "utr",
                    "via": "rtd",
                    "time": "08:30:00",
                },
                blocking=True,
            )

            mock_add.assert_called_once_with(
                {
                    "name": "Complex Route",
                    "from": "AMS",
                    "to": "UTR",
                    "via": "RTD",
                    "time": "08:30:00",
                }
            )


async def test_add_route_service_without_optional_params(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test the add_route service without optional parameters."""
    # Create a fully mocked config entry with the required attributes
    mock_entry = MagicMock()
    mock_entry.runtime_data = {
        "coordinator": init_integration.runtime_data["coordinator"]
    }
    mock_state = MagicMock()
    mock_state.name = "LOADED"
    mock_entry.state = mock_state

    # Patch the config entries lookup to return our mock entry
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_entries"
    ) as mock_entries:
        mock_entries.return_value = [mock_entry]

        with patch.object(
            init_integration.runtime_data["coordinator"], "async_add_route"
        ) as mock_add:
            await hass.services.async_call(
                DOMAIN,
                "add_route",
                {
                    "name": "Simple Route",
                    "from": "ams",
                    "to": "utr",
                },
                blocking=True,
            )

            mock_add.assert_called_once_with(
                {
                    "name": "Simple Route",
                    "from": "AMS",
                    "to": "UTR",
                }
            )


async def test_remove_route_service_no_integration(hass: HomeAssistant) -> None:
    """Test remove_route service when no integration is configured."""
    await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(
        ServiceValidationError, match="No Nederlandse Spoorwegen integration found"
    ):
        await hass.services.async_call(
            DOMAIN,
            "remove_route",
            {"name": "Test Route"},
            blocking=True,
        )


async def test_remove_route_service_integration_not_loaded(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test remove_route service when integration is not loaded."""
    await async_setup_component(hass, DOMAIN, {})

    # Create a fully mocked config entry with NOT_LOADED state
    mock_entry = MagicMock()
    mock_state = MagicMock()
    mock_state.name = "NOT_LOADED"
    mock_entry.state = mock_state

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_entries"
    ) as mock_entries:
        mock_entries.return_value = [mock_entry]

        with pytest.raises(
            ServiceValidationError,
            match="Nederlandse Spoorwegen integration not loaded",
        ):
            await hass.services.async_call(
                DOMAIN,
                "remove_route",
                {"name": "Test Route"},
                blocking=True,
            )
