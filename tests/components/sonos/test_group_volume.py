"""Tests for the Sonos group volume number entity."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er


async def _setup_numbers_only(async_setup_sonos) -> None:
    """Load only the Number platform (matches Sonos test pattern)."""
    with patch("homeassistant.components.sonos.PLATFORMS", [Platform.NUMBER]):
        await async_setup_sonos()


def _find_group_volume_entity_id(entity_registry: er.EntityRegistry) -> str | None:
    """Return entity_id for the group-volume number (unique_id ends with -group_volume)."""
    for ent in entity_registry.entities.values():
        if ent.platform != "sonos" or not ent.entity_id.startswith("number."):
            continue
        uid = (ent.unique_id or "").lower()
        if uid.endswith("-group_volume"):
            return ent.entity_id
    return None


@pytest.mark.usefixtures("async_setup_sonos")
async def test_group_volume_entity_created(
    async_setup_sonos, entity_registry: er.EntityRegistry
) -> None:
    """The group volume number entity should be created."""
    await _setup_numbers_only(async_setup_sonos)

    group_eid = _find_group_volume_entity_id(entity_registry)
    assert group_eid, "Expected a Sonos group volume number entity"
    assert group_eid.startswith("number.")


@pytest.mark.usefixtures("async_setup_sonos")
async def test_group_volume_sets_backend_and_updates_state(
    hass: HomeAssistant, async_setup_sonos, entity_registry: er.EntityRegistry, soco
) -> None:
    """Setting 0.33 writes group.volume=33 and updates HA state optimistically."""
    # Provide a writable group with a volume attribute
    if getattr(soco, "group", None) is None:
        soco.group = SimpleNamespace(volume=0)
    elif not hasattr(soco.group, "volume"):
        soco.group.volume = 0

    await _setup_numbers_only(async_setup_sonos)

    group_eid = _find_group_volume_entity_id(entity_registry)
    assert group_eid, "Could not find group volume number entity_id"

    await hass.services.async_call(
        "number", "set_value", {"entity_id": group_eid, "value": 0.33}, blocking=True
    )

    # Backend write scaling: 0.33 -> 33
    assert soco.group.volume == 33

    # Optimistic state update (0.0–1.0)
    state = hass.states.get(group_eid)
    assert state is not None
    assert float(state.state) == pytest.approx(0.33, rel=1e-2)


@pytest.mark.usefixtures("async_setup_sonos")
async def test_group_volume_rejects_out_of_range_and_rounds(
    hass: HomeAssistant, async_setup_sonos, entity_registry: er.EntityRegistry, soco
) -> None:
    """Number platform rejects out-of-range; in-range 0.495 rounds to 50%."""
    if getattr(soco, "group", None) is None:
        soco.group = SimpleNamespace(volume=0)
    elif not hasattr(soco.group, "volume"):
        soco.group.volume = 0

    await _setup_numbers_only(async_setup_sonos)

    group_eid = _find_group_volume_entity_id(entity_registry)
    assert group_eid

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
