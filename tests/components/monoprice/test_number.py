"""Tests for the Monoprice number platform."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.monoprice.const import CONF_NOT_FIRST_RUN, DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import setup_integration

ZONE_1_BASS = "number.zone_11_bass"
ZONE_2_BASS = "number.zone_12_bass"


async def _update_zone(hass: HomeAssistant, entity_id: str) -> None:
    """Poll a zone and let the dispatched update reach its numbers."""
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_monoprice: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all number entities."""
    await setup_integration(hass, mock_config_entry)

    number_entries = [
        entity_entry
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entity_entry.domain == NUMBER_DOMAIN
    ]
    assert len(number_entries) == 18
    for entity_entry in number_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("entity_id", "value", "setter", "amplifier_value"),
    [
        pytest.param("number.zone_11_bass", -7, "set_bass", 0, id="bass_minimum"),
        pytest.param("number.zone_11_bass", 7, "set_bass", 14, id="bass_maximum"),
        pytest.param("number.zone_11_treble", 3, "set_treble", 10, id="treble"),
        pytest.param("number.zone_11_balance", -10, "set_balance", 0, id="left"),
        pytest.param("number.zone_11_balance", 0, "set_balance", 10, id="centre"),
        pytest.param("number.zone_11_balance", 10, "set_balance", 20, id="right"),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_monoprice: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: int,
    setter: str,
    amplifier_value: int,
) -> None:
    """Test the value is sent to the amplifier with its own scale."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    getattr(mock_monoprice, setter).assert_called_once_with(11, amplifier_value)
    assert hass.states.get(entity_id).state == str(value)


async def test_value_follows_zone_update(
    hass: HomeAssistant,
    mock_monoprice: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a poll of the zone updates the numbers without more queries."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ZONE_1_BASS).state == "2"

    mock_monoprice.zones[11].bass = 14
    mock_monoprice.zone_status.reset_mock()
    await _update_zone(hass, "media_player.zone_11")

    assert hass.states.get(ZONE_1_BASS).state == "7"
    mock_monoprice.zone_status.assert_called_once_with(11)


async def test_unavailable_until_first_poll(
    hass: HomeAssistant,
    mock_monoprice: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the numbers of an amplifier set up before wait for the first poll."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_NOT_FIRST_RUN: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ZONE_1_BASS).state == STATE_UNAVAILABLE

    await _update_zone(hass, "media_player.zone_11")
    assert hass.states.get(ZONE_1_BASS).state == "2"


async def test_unavailable_while_zone_is_off(
    hass: HomeAssistant,
    mock_monoprice: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the numbers follow the power of their zone."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ZONE_2_BASS).state == STATE_UNAVAILABLE

    mock_monoprice.zones[12].power = True
    await _update_zone(hass, "media_player.zone_12")
    assert hass.states.get(ZONE_2_BASS).state == "2"

    mock_monoprice.zones[12].power = False
    await _update_zone(hass, "media_player.zone_12")
    assert hass.states.get(ZONE_2_BASS).state == STATE_UNAVAILABLE


async def test_extension_zones(
    hass: HomeAssistant,
    mock_monoprice: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only the detected zones of a chained amplifier get numbers."""
    mock_monoprice.zones[21] = replace(mock_monoprice.zones[11], zone=21)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.zone_21_bass").state == "2"
    assert entity_registry.async_get("number.zone_22_bass") is None


async def test_disabled_zone_has_no_numbers(
    hass: HomeAssistant,
    mock_monoprice: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a zone whose media player was disabled gets no numbers."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        MEDIA_PLAYER_DOMAIN,
        DOMAIN,
        f"{mock_config_entry.entry_id}_13",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ZONE_1_BASS) is not None
    assert entity_registry.async_get("number.zone_13_bass") is None
