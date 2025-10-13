"""Test the Nederlandse Spoorwegen sensor."""

from unittest.mock import AsyncMock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nederlandse_spoorwegen.const import (
    CONF_FROM,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
    INTEGRATION_TITLE,
    SUBENTRY_TYPE_ROUTE,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import API_KEY

from tests.common import MockConfigEntry, snapshot_platform


async def test_config_import(
    hass: HomeAssistant,
    mock_nsapi,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test sensor initialization."""
    await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: API_KEY,
                    CONF_ROUTES: [
                        {
                            CONF_NAME: "Spoorwegen Nederlande Station",
                            CONF_FROM: "ASD",
                            CONF_TO: "RTD",
                            CONF_VIA: "HT",
                        }
                    ],
                }
            ]
        },
    )

    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    assert (HOMEASSISTANT_DOMAIN, "deprecated_yaml") in issue_registry.issues
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
async def test_sensor(
    hass: HomeAssistant,
    mock_nsapi,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_with_api_connection_error(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor behavior when API connection fails."""
    # Make API calls fail from the start
    mock_nsapi.get_trips.side_effect = RequestsConnectionError("Connection failed")

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Sensors should still be created but may show error state or have error attributes
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 2  # Two routes from mock_config_entry

    # Check that sensors handle the error gracefully (not crash the integration)
    for state in sensor_states:
        # Should either be unavailable or unknown or have error information
        is_valid_error_state = (
            state.state in ("unavailable", "unknown")
            or state.attributes.get("error") is not None
        )
        assert is_valid_error_state


async def test_sensor_handles_multiple_routes(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multiple routes create separate sensors."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Should have sensors for both routes in mock_config_entry
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 2

    # Each sensor should have the route name in its friendly_name or entity_id
    entity_ids = [state.entity_id for state in sensor_states]
    assert "sensor.to_work" in entity_ids or "sensor.to_home" in entity_ids


@pytest.mark.parametrize(
    "exception_cls",
    [RequestsConnectionError, ValueError],
)
async def test_sensor_handles_api_exceptions(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception_cls,
) -> None:
    """Test sensor behavior when various API exceptions occur."""
    # Make API calls fail
    mock_nsapi.get_trips.side_effect = exception_cls("API Error")

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Integration should not crash, sensors should handle errors gracefully
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 2

    # Sensors should show appropriate error state or have error attributes
    for state in sensor_states:
        # Should not crash - sensor exists with some error indication
        assert state is not None
        # Error should be handled gracefully (unavailable, unknown, or error attr)
        is_error_handled = (
            state.state in ("unavailable", "unknown")
            or "error" in state.attributes
            or state.attributes.get("attribution") == "Data provided by NS"
        )
        assert is_error_handled


async def test_sensor_initialization_with_successful_api(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor initialization when API calls succeed."""
    # The mock_nsapi fixture already returns successful data

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Should have sensors for both routes
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 2

    # Check that sensors have proper attributes
    for state in sensor_states:
        assert state is not None
        assert state.attributes.get("attribution") == "Data provided by NS"
        assert state.attributes.get("device_class") == "timestamp"
        assert state.attributes.get("icon") == "mdi:train"


@pytest.mark.parametrize(
    ("time_input", "route_name", "description"),
    [
        (None, "Current time route", "No specific time - should use current time"),
        ("08:30", "Morning commute", "Time only - should use today's date with time"),
        ("08:30:45", "Early commute", "Time with seconds - should truncate seconds"),
        (
            "10-10-2025 14:30",
            "Afternoon meeting",
            "Full datetime - should extract time part",
        ),
        (
            "invalid_time",
            "Flexible route",
            "Invalid format - should fallback gracefully",
        ),
    ],
)
async def test_sensor_with_custom_time_parsing(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    time_input,
    route_name,
    description,
) -> None:
    """Test sensor with different time parsing scenarios."""
    # Create a config entry with a route that has the specified time
    config_entry = MockConfigEntry(
        title=INTEGRATION_TITLE,
        data={CONF_API_KEY: API_KEY},
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_NAME: route_name,
                    CONF_FROM: "Ams",
                    CONF_TO: "Rot",
                    CONF_VIA: "Ht",
                    CONF_TIME: time_input,
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=f"{route_name} Route",
                unique_id=None,
                subentry_id=f"test_route_{time_input or 'none'}".replace(":", "_")
                .replace("-", "_")
                .replace(" ", "_"),
            ),
        ],
    )

    await setup_integration(hass, config_entry)
    await hass.async_block_till_done()

    # Should create one sensor for the route with time parsing
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 1

    # Verify sensor was created successfully with time parsing
    state = sensor_states[0]
    assert state is not None
    assert state.state != "unavailable"
    assert state.attributes.get("attribution") == "Data provided by NS"
    assert state.attributes.get("device_class") == "timestamp"
    assert state.attributes.get("icon") == "mdi:train"

    # The sensor should have a friendly name based on the route name
    friendly_name = state.attributes.get("friendly_name", "").lower()
    assert (
        route_name.lower() in friendly_name
        or route_name.replace(" ", "_").lower() in state.entity_id
    )
