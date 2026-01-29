"""Test the Nina binary sensor."""

from __future__ import annotations

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nina.const import ATTR_HEADLINE
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_single_platform

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA binary sensors."""
    await setup_single_platform(
        hass, mock_config_entry, Platform.BINARY_SENSOR, mock_nina_class, nina_warnings
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensors_without_corona_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_no_filter: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA binary sensors without the corona filter."""

    await setup_single_platform(
        hass,
        mock_config_entry_no_filter,
        Platform.BINARY_SENSOR,
        mock_nina_class,
        nina_warnings,
    )

    state_w1 = hass.states.get("binary_sensor.nina_warning_aach_stadt_1")

    assert state_w1.state == STATE_ON
    assert (
        state_w1.attributes.get(ATTR_HEADLINE)
        == "Corona-Verordnung des Landes: Warnstufe durch Landesgesundheitsamt ausgerufen"
    )

    state_w2 = hass.states.get("binary_sensor.nina_warning_aach_stadt_2")

    assert state_w2.state == STATE_ON
    assert state_w2.attributes.get(ATTR_HEADLINE) == "Ausfall Notruf 112"

    state_w3 = hass.states.get("binary_sensor.nina_warning_aach_stadt_3")

    assert state_w3.state == STATE_OFF  # Warning expired

    state_w4 = hass.states.get("binary_sensor.nina_warning_aach_stadt_4")

    assert state_w4.state == STATE_OFF

    state_w5 = hass.states.get("binary_sensor.nina_warning_aach_stadt_5")

    assert state_w5.state == STATE_OFF


async def test_binary_sensors_with_area_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_area_filter: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA binary sensors with a restrictive area filter."""

    await setup_single_platform(
        hass,
        mock_config_entry_area_filter,
        Platform.BINARY_SENSOR,
        mock_nina_class,
        nina_warnings,
    )

    state_w1 = hass.states.get("binary_sensor.nina_warning_aach_stadt_1")

    assert state_w1.state == STATE_ON
    assert state_w1.attributes.get(ATTR_HEADLINE) == "Ausfall Notruf 112"

    state_w2 = hass.states.get("binary_sensor.nina_warning_aach_stadt_2")

    assert state_w2.state == STATE_OFF

    state_w3 = hass.states.get("binary_sensor.nina_warning_aach_stadt_3")

    assert state_w3.state == STATE_OFF

    state_w4 = hass.states.get("binary_sensor.nina_warning_aach_stadt_4")

    assert state_w4.state == STATE_OFF

    state_w5 = hass.states.get("binary_sensor.nina_warning_aach_stadt_5")

    assert state_w5.state == STATE_OFF
