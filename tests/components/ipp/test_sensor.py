"""Tests for the IPP sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pyipp import IPPError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time("2019-11-11 09:10:32+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the creation and values of the IPP sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the disabled by default IPP sensors."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", "ipp", f"{init_integration.unique_id}_uptime"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is None

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_missing_entry_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
) -> None:
    """Test the unique_id of IPP sensor when printer is missing identifiers."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=None)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get("sensor.test_ha_1000_series")
    assert entity
    assert entity.unique_id == f"{mock_config_entry.entry_id}_printer"


@pytest.mark.parametrize(
    "execute_response",
    [
        {"printers": [{}]},  # Empty printer dict
        {"printers": []},  # Empty printers list
        {},  # Missing printers key
        {
            "printers": [
                {
                    "printer-pages-completed": "",
                    "printer-impressions-completed": "",
                    "printer-media-sheets-completed": "",
                    "printer-impressions-completed-col": "",
                }
            ]
        },  # Out-of-band values (unknown / no-value) decoded by pyipp
    ],
)
async def test_no_page_count_sensors_when_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_ipp: MagicMock,
    execute_response: dict[str, Any],
) -> None:
    """Test that page count sensors are not created when printer doesn't support them."""
    mock_ipp.execute.return_value = execute_response
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    unique_id = mock_config_entry.unique_id
    for key in (
        "pages_completed",
        "impressions_completed",
        "media_sheets_completed",
        "impressions_completed_monochrome",
        "impressions_completed_full_color",
    ):
        assert not entity_registry.async_get_entity_id(
            "sensor", "ipp", f"{unique_id}_{key}"
        )


async def test_page_count_sensors_with_partial_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_ipp: MagicMock,
) -> None:
    """Test only the reported page counts get sensors.

    Attributes and collection members the printer reports as out-of-band
    values are decoded as empty strings by pyipp and must be skipped.
    """
    mock_ipp.execute.return_value = {
        "printers": [
            {
                "printer-pages-completed": "",
                "printer-impressions-completed": 2468,
                "printer-impressions-completed-col": {
                    "monochrome": 1500,
                    "full-color": "",
                },
            }
        ],
    }
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = mock_config_entry.unique_id
    for key in (
        "pages_completed",
        "media_sheets_completed",
        "impressions_completed_full_color",
    ):
        assert not entity_registry.async_get_entity_id(
            "sensor", "ipp", f"{unique_id}_{key}"
        )

    state = hass.states.get("sensor.test_ha_1000_series_impressions_completed")
    assert state
    assert state.state == "2468"

    state = hass.states.get(
        "sensor.test_ha_1000_series_monochrome_impressions_completed"
    )
    assert state
    assert state.state == "1500"


@pytest.mark.parametrize(
    ("execute_side_effect", "execute_response", "expected_state"),
    [
        pytest.param(IPPError("boom"), None, "1234", id="error-retains-previous"),
        pytest.param(None, {"printers": [{}]}, STATE_UNKNOWN, id="empty-clears"),
    ],
)
async def test_page_counts_after_fetch_issue(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_ipp: MagicMock,
    execute_side_effect: IPPError | None,
    execute_response: dict[str, Any] | None,
    expected_state: str,
) -> None:
    """Test page count sensor values after a failed or empty fetch.

    A failed request keeps the previous values, while a successful response
    without page count attributes clears them.
    """
    assert hass.states.get("sensor.test_ha_1000_series_pages_completed").state == "1234"

    mock_ipp.execute.side_effect = execute_side_effect
    mock_ipp.execute.return_value = execute_response
    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_ha_1000_series_pages_completed").state
        == expected_state
    )
