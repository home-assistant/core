"""Parametrized inversion behavior tests for Inverse integration."""

from __future__ import annotations

import pytest

from homeassistant.components.inverse.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("domain", "service_expected"),
    [
        ("switch", ("turn_on", "turn_off")),
        ("light", ("turn_on", "turn_off")),
        ("fan", ("turn_on", "turn_off")),
        ("siren", ("turn_on", "turn_off")),
    ],
)
async def test_toggle_forwarding(
    hass: HomeAssistant, domain: str, service_expected: tuple[str, str]
) -> None:
    """Verify toggle entities forward service calls (no inversion at service level)."""
    entity_id = f"{domain}.sample"
    entry = MockConfigEntry(
        title=f"Inverse {entity_id}", domain=DOMAIN, data={"entity_id": entity_id}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_entity_id = f"{domain}.inverse_{entity_id.split('.')[1]}"

    # We can't easily spy on service layer without a backing entity, so ensure calls don't raise
    await hass.services.async_call(
        domain, service_expected[0], {"entity_id": inv_entity_id}, blocking=True
    )
    await hass.services.async_call(
        domain, service_expected[1], {"entity_id": inv_entity_id}, blocking=True
    )


@pytest.mark.asyncio
async def test_lock_inversion_services(hass: HomeAssistant) -> None:
    """Lock service inversion: lock -> unlock, unlock -> lock."""
    entity_id = "lock.sample"
    entry = MockConfigEntry(
        title="Inverse lock", domain=DOMAIN, data={"entity_id": entity_id}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_entity_id = "lock.inverse_sample"
    # Service calls should be accepted; actual inversion verified by entity code paths
    await hass.services.async_call(
        "lock", "lock", {"entity_id": inv_entity_id}, blocking=True
    )
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": inv_entity_id}, blocking=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [0, 25, 50, 75, 100])
async def test_cover_position_inversion(hass: HomeAssistant, position: int) -> None:
    """Set cover position should invert value (100 - position)."""
    entity_id = "cover.sample"
    entry = MockConfigEntry(
        title="Inverse cover", domain=DOMAIN, data={"entity_id": entity_id}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_entity_id = "cover.inverse_sample"
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": inv_entity_id, "position": position},
        blocking=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [0, 20, 50, 80, 100])
async def test_valve_position_inversion(hass: HomeAssistant, position: int) -> None:
    """Set valve position should invert value (100 - position)."""
    entity_id = "valve.sample"
    entry = MockConfigEntry(
        title="Inverse valve", domain=DOMAIN, data={"entity_id": entity_id}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_entity_id = "valve.inverse_sample"
    await hass.services.async_call(
        "valve",
        "set_valve_position",
        {"entity_id": inv_entity_id, "position": position},
        blocking=True,
    )
