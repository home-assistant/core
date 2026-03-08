"""Test the Nina binary sensor."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nina.const import (
    ATTR_HEADLINE,
    CONF_AREA_FILTER,
    CONF_FILTERS,
    CONF_HEADLINE_FILTER,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    DOMAIN,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform

ENTRY_DATA_NO_CORONA: dict[str, Any] = {
    CONF_MESSAGE_SLOTS: 5,
    CONF_REGIONS: {"083350000000": "Aach, Stadt"},
    CONF_FILTERS: {
        CONF_HEADLINE_FILTER: "/(?!)/",
        CONF_AREA_FILTER: ".*",
    },
}

ENTRY_DATA_SPECIFIC_AREA: dict[str, Any] = {
    CONF_MESSAGE_SLOTS: 5,
    CONF_REGIONS: {"083350000000": "Aach, Stadt"},
    CONF_FILTERS: {
        CONF_HEADLINE_FILTER: "/(?!)/",
        CONF_AREA_FILTER: ".*nagold.*",
    },
}


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA sensors."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_without_corona_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA sensors without the corona filter."""

    conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=ENTRY_DATA_NO_CORONA,
        version=1,
        minor_version=3,
    )
    conf_entry.add_to_hass(hass)

    await setup_platform(hass, conf_entry, mock_nina_class, nina_warnings)

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

    assert state_w3.state == STATE_OFF

    state_w4 = hass.states.get("binary_sensor.nina_warning_aach_stadt_4")

    assert state_w4.state == STATE_OFF

    state_w5 = hass.states.get("binary_sensor.nina_warning_aach_stadt_5")

    assert state_w5.state == STATE_OFF


async def test_sensors_with_area_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test the creation and values of the NINA sensors with a restrictive area filter."""

    conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=ENTRY_DATA_SPECIFIC_AREA,
        version=1,
        minor_version=3,
    )
    conf_entry.add_to_hass(hass)

    await setup_platform(hass, conf_entry, mock_nina_class, nina_warnings)

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
