"""Test the Nina sensor."""

from unittest.mock import AsyncMock

from pynina import Warning
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_single_platform

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA sensors."""
    await setup_single_platform(
        hass, mock_config_entry, Platform.SENSOR, mock_nina_class, nina_warnings
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_without_corona_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_default_filter: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA sensors without the corona filter."""
    await setup_single_platform(
        hass,
        mock_config_entry_default_filter,
        Platform.SENSOR,
        mock_nina_class,
        nina_warnings,
    )

    state_w1 = hass.states.get("sensor.aach_stadt_severity_1")

    assert state_w1.state == "minor"

    state_w2 = hass.states.get("sensor.aach_stadt_severity_2")

    assert state_w2.state == "minor"

    state_w3 = hass.states.get("sensor.aach_stadt_severity_3")

    assert state_w3.state == STATE_UNAVAILABLE  # Warning expired

    state_w4 = hass.states.get("sensor.aach_stadt_severity_4")

    assert state_w4.state == STATE_UNAVAILABLE

    state_w5 = hass.states.get("sensor.aach_stadt_severity_5")

    assert state_w5.state == STATE_UNAVAILABLE


async def test_sensors_with_area_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_area_filter: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA sensors with a restrictive area filter."""
    await setup_single_platform(
        hass,
        mock_config_entry_area_filter,
        Platform.SENSOR,
        mock_nina_class,
        nina_warnings,
    )

    state_w1 = hass.states.get("sensor.aach_stadt_severity_1")

    assert state_w1.state == "minor"

    state_w2 = hass.states.get("sensor.aach_stadt_severity_2")

    assert state_w2.state == STATE_UNAVAILABLE

    state_w3 = hass.states.get("sensor.aach_stadt_severity_3")

    assert state_w3.state == STATE_UNAVAILABLE

    state_w4 = hass.states.get("sensor.aach_stadt_severity_4")

    assert state_w4.state == STATE_UNAVAILABLE

    state_w5 = hass.states.get("sensor.aach_stadt_severity_5")

    assert state_w5.state == STATE_UNAVAILABLE
