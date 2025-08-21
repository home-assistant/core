"""Tests for the Sonos group volume number entity."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.sonos.const import (
    SONOS_SPEAKER_ACTIVITY,
    SONOS_STATE_UPDATED,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send


async def _setup_numbers_only(async_setup_sonos) -> None:
    """Load only the Number platform (matches Sonos test pattern)."""
    with patch("homeassistant.components.sonos.PLATFORMS", [Platform.NUMBER]):
        await async_setup_sonos()


def _expected_group_volume_entity_id() -> str:
    """The translated entity_id for group volume (zone_a fixture)."""
    return "number.zone_a_group_volume"


async def test_group_volume_entity_created(
    hass: HomeAssistant, async_setup_sonos, entity_registry: er.EntityRegistry
) -> None:
    """The group volume number entity should be created with translated id."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    assert entity_registry.async_get(group_eid) is not None
    state = hass.states.get(group_eid)
    assert state is not None, "Expected a Sonos group volume number entity"
    assert group_eid.startswith("number.")
    assert "friendly_name" in state.attributes


async def test_group_volume_sets_backend_and_updates_state(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Setting 0.33 writes group.volume=33; HA state updates after coordinator event."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    await hass.services.async_call(
        "number", "set_value", {"entity_id": group_eid, "value": 0.33}, blocking=True
    )

    # Backend write scaling: 0.33 -> 33
    assert soco.group.volume == 33

    # Entity updates when it hears a coordinator state update (coord is zone_a).
    async_dispatcher_send(hass, f"{SONOS_STATE_UPDATED}-{soco.uid}")
    await hass.async_block_till_done()

    state = hass.states.get(group_eid)
    assert state is not None
    assert float(state.state) == pytest.approx(0.33, rel=1e-2)


async def test_group_volume_rejects_out_of_range_and_rounds(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Number platform rejects out-of-range; in-range 0.495 rounds to 50%."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    # Out-of-range inputs are rejected by HA before entity method runs
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": group_eid, "value": -0.2},
            blocking=True,
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": group_eid, "value": 1.1}, blocking=True
        )

    # In-range rounding: 0.495 -> round(49.5) == 50
    await hass.services.async_call(
        "number", "set_value", {"entity_id": group_eid, "value": 0.495}, blocking=True
    )
    assert soco.group.volume == 50


async def test_group_volume_updates_on_activity(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Group volume updates when an activity event is processed."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    # Change underlying group volume (0–100) and simulate an activity update
    # from the coordinator (zone_a in the fixture).
    soco.group.volume = 55
    async_dispatcher_send(hass, f"{SONOS_STATE_UPDATED}-{soco.uid}")
    await hass.async_block_till_done()

    state = hass.states.get(group_eid)
    assert state is not None
    assert abs(float(state.state) - 0.55) < 0.01


async def test_group_volume_fallback_polling(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Group volume updates via polling if no subscription events arrive."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    # Simulate a local-activity event on this speaker (entity listens and polls).
    soco.group.volume = 33
    async_dispatcher_send(hass, f"{SONOS_SPEAKER_ACTIVITY}-{soco.uid}")
    await hass.async_block_till_done()

    state = hass.states.get(group_eid)
    assert state is not None
    assert abs(float(state.state) - 0.33) < 0.01


async def test_group_volume_number_metadata(
    hass: HomeAssistant, async_setup_sonos
) -> None:
    """Group volume number has the expected range, step, and mode."""
    await _setup_numbers_only(async_setup_sonos)
    eid = _expected_group_volume_entity_id()
    state = hass.states.get(eid)
    assert state is not None

    attrs = state.attributes
    # Range 0.0–1.0 with 0.01 step and slider mode
    assert attrs.get("min") == 0.0
    assert attrs.get("max") == 1.0
    assert attrs.get("step") == 0.01
    assert attrs.get("mode") == "slider"

    # No unit/device_class expected for a normalized ratio
    assert "unit_of_measurement" not in attrs
    assert "device_class" not in attrs
