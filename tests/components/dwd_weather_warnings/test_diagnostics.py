"""Tests for the diagnostics of the dwd_weather_warnings integration."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.dwd_weather_warnings.const import (
    API_ATTR_WARNING_COLOR,
    API_ATTR_WARNING_DESCRIPTION,
    API_ATTR_WARNING_END,
    API_ATTR_WARNING_HEADLINE,
    API_ATTR_WARNING_INSTRUCTION,
    API_ATTR_WARNING_LEVEL,
    API_ATTR_WARNING_NAME,
    API_ATTR_WARNING_PARAMETERS,
    API_ATTR_WARNING_START,
    API_ATTR_WARNING_TYPE,
    CONF_REGION_DEVICE_TRACKER,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

MOCK_WARNING = {
    API_ATTR_WARNING_NAME: "STURMBÖEN",
    API_ATTR_WARNING_TYPE: 52,
    API_ATTR_WARNING_LEVEL: 2,
    API_ATTR_WARNING_HEADLINE: "Amtliche WARNUNG: STURMBÖEN",
    API_ATTR_WARNING_DESCRIPTION: "Es treten Sturmböen um 70 km/h auf.",
    API_ATTR_WARNING_INSTRUCTION: None,
    API_ATTR_WARNING_START: datetime(2026, 11, 22, 10, 0, tzinfo=UTC),
    API_ATTR_WARNING_END: datetime(2026, 11, 22, 18, 0, tzinfo=UTC),
    API_ATTR_WARNING_PARAMETERS: {"Böen": "~70 [km/h]"},
    API_ATTR_WARNING_COLOR: "#ffaf00",
}


async def test_diagnostics_identifier(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_identifier_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for an entry configured with a region identifier."""
    mock_dwdwfsapi.data_valid = True
    mock_dwdwfsapi.warncell_id = 807111000
    mock_dwdwfsapi.warncell_name = "Kreis Mayen-Koblenz"
    mock_dwdwfsapi.last_update = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)
    mock_dwdwfsapi.current_warning_level = 2
    mock_dwdwfsapi.current_warnings = [MOCK_WARNING]
    mock_dwdwfsapi.expected_warning_level = 0
    mock_dwdwfsapi.expected_warnings = []
    entry = await init_integration(hass, mock_identifier_entry)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


async def test_diagnostics_device_tracker(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mock_tracker_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics redact the device tracker of a tracker based entry."""
    mock_tracker_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "device_tracker",
        mock_tracker_entry.domain,
        "uuid",
        suggested_object_id="test_gps",
        config_entry=mock_tracker_entry,
    )
    hass.states.async_set(
        mock_tracker_entry.data[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LATITUDE: 50.180454, ATTR_LONGITUDE: 7.610263},
    )
    await hass.config_entries.async_setup(mock_tracker_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_tracker_entry)
        == snapshot
    )
