"""Test the Hunter Douglas PowerView schedule switch platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .const import MOCK_MAC

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_schedule_switches_created_v2(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that schedule switches are created for Gen2."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 12 scheduled events in the Gen2 fixture
    switch_ids = hass.states.async_entity_ids("switch")
    assert len(switch_ids) == 12


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [3])
async def test_schedule_switches_created_v3(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that schedule switches are created for Gen3."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 9 automations in the Gen3 fixture
    switch_ids = hass.states.async_entity_ids("switch")
    assert len(switch_ids) == 9


def _find_switch_by_scene(hass: HomeAssistant, scene_name: str) -> list:
    """Return all switch states whose scene_name attribute matches."""
    return [
        state
        for entity_id in hass.states.async_entity_ids("switch")
        if (state := hass.states.get(entity_id)) is not None
        and state.attributes.get("scene_name") == scene_name
    ]


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_schedule_switch_state(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test switch state reflects the enabled field."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Event 37484 is the only enabled=true event (Open Kitchen scene)
    enabled_switches = _find_switch_by_scene(hass, "Open Kitchen")
    assert len(enabled_switches) == 1
    assert enabled_switches[0].state == STATE_ON

    # Open Bed 4 has 3 scheduled events, all disabled
    disabled_switches = _find_switch_by_scene(hass, "Open Bed 4")
    assert len(disabled_switches) == 3
    assert all(s.state == STATE_OFF for s in disabled_switches)


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_schedule_switch_attributes(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that schedule switches expose execution time and days attributes."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    switches = _find_switch_by_scene(hass, "Open Kitchen")
    assert len(switches) == 1
    state = switches[0]
    assert "execution_time" in state.attributes
    assert "execution_days" in state.attributes
    assert state.attributes["scene_name"] == "Open Kitchen"


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_schedule_switch_turn_on(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test turning on a schedule switch enables the scheduled event."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    switches = _find_switch_by_scene(hass, "Open Kitchen")
    assert len(switches) == 1
    entity_id = switches[0].entity_id

    with patch(
        "homeassistant.components.hunterdouglas_powerview.switch.Automation.set_state",
        new_callable=AsyncMock,
    ) as mock_set_state:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_set_state.assert_called_once_with(True)


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_schedule_switch_turn_off(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test turning off a schedule switch disables the scheduled event."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    switches = _find_switch_by_scene(hass, "Open Kitchen")
    assert len(switches) == 1
    entity_id = switches[0].entity_id

    with patch(
        "homeassistant.components.hunterdouglas_powerview.switch.Automation.set_state",
        new_callable=AsyncMock,
    ) as mock_set_state:
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_set_state.assert_called_once_with(False)


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [2])
async def test_schedule_switch_scene_reference(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that schedule switches expose scene PV ID and HA entity ID."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Event 37484 references scene 64679 ("Open Kitchen")
    switches = _find_switch_by_scene(hass, "Open Kitchen")
    assert len(switches) == 1
    state = switches[0]
    assert state.attributes["scene_id"] == 64679
    assert state.attributes["scene_entity_id"] == "scene.powerview_generation_2_open_kitchen"


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [3])
async def test_schedule_switch_scene_reference_v3(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that Gen3 schedule switches expose scene PV ID and HA entity ID."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Automation 437 references scene 220 ("Close Bed 4")
    switches = _find_switch_by_scene(hass, "Close Bed 4")
    assert len(switches) == 1
    state = switches[0]
    assert state.attributes["scene_id"] == 220
    assert state.attributes["scene_entity_id"] == "scene.powerview_generation_3_close_bed_4"


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1])
async def test_no_schedule_switches_for_v1(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that no schedule switches are created for Gen1."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids_count("switch") == 0
