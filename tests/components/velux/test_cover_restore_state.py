"""Tests for the Velux cover restore-state seeding."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.const import (
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State

from . import update_callback_entity

from tests.common import MockConfigEntry, mock_restore_cache


async def _setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the velux integration with only the cover platform loaded."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.velux.PLATFORMS", [Platform.COVER]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_cover_seeds_position_from_live_pyvlx_when_known_at_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: AsyncMock,
    mock_window: AsyncMock,
) -> None:
    """If pyvlx already knows the position, seed the restore cache from it.

    Subsequent transient UNKNOWN frames must then fall back to that cached
    live value instead of dropping the entity to `unknown`.
    """
    # pyvlx already has a concrete position at startup.
    mock_window.position.position_percent = 30  # HA = 70
    mock_window.position.known = True
    mock_window.position.closed = False

    await _setup(hass, mock_config_entry)

    entity_id = "cover.test_window"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 70

    # pyvlx transitions back to UNKNOWN (e.g. reconnect mid-session).
    mock_window.position.known = False
    await update_callback_entity(hass, mock_window)

    state = hass.states.get(entity_id)
    assert state is not None
    # Fallback uses the cached live value rather than going `unknown`.
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 70


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_cover_seeds_position_from_persisted_attribute_when_unknown_at_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: AsyncMock,
    mock_window: AsyncMock,
) -> None:
    """When pyvlx is UNKNOWN at startup, seed from the persisted attribute.

    Reproduces the KLF200-reboot scenario: after async_unload_entry the
    gateway is rebooted and reports `current_position = UNKNOWN` for tens
    of seconds. HA persists the previous run's attribute and we use it to
    avoid the `unknown` window.
    """
    mock_window.position.known = False

    mock_restore_cache(
        hass,
        [
            State(
                "cover.test_window",
                STATE_OPEN,
                attributes={ATTR_CURRENT_POSITION: 70},
            ),
        ],
    )

    await _setup(hass, mock_config_entry)

    state = hass.states.get("cover.test_window")
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 70


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_cover_seeds_position_from_attribute_even_if_persisted_state_was_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: AsyncMock,
    mock_window: AsyncMock,
) -> None:
    """A persisted attribute is honoured even if the persisted state was unknown.

    HA may have written ``state="unknown"`` during a previous post-restart
    UNKNOWN window while the ``current_position`` attribute was still a
    usable number. We restore from the attribute regardless of the state
    string.
    """
    mock_window.position.known = False

    mock_restore_cache(
        hass,
        [
            State(
                "cover.test_window",
                STATE_UNKNOWN,
                attributes={ATTR_CURRENT_POSITION: 0},
            ),
        ],
    )

    await _setup(hass, mock_config_entry)

    state = hass.states.get("cover.test_window")
    assert state is not None
    assert state.state == STATE_CLOSED
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
@pytest.mark.parametrize(
    "persisted_attribute",
    [None, "not-a-number", -10, 150],
    ids=["missing", "string", "below_zero", "above_hundred"],
)
async def test_cover_keeps_unknown_when_no_usable_seed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: AsyncMock,
    mock_window: AsyncMock,
    persisted_attribute: object,
) -> None:
    """Without a usable live or persisted position the entity stays unknown."""
    mock_window.position.known = False

    attributes = (
        {ATTR_CURRENT_POSITION: persisted_attribute}
        if persisted_attribute is not None
        else {}
    )
    mock_restore_cache(
        hass,
        [State("cover.test_window", STATE_UNAVAILABLE, attributes=attributes)],
    )

    await _setup(hass, mock_config_entry)

    state = hass.states.get("cover.test_window")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_cover_refreshes_cache_on_live_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: AsyncMock,
    mock_window: AsyncMock,
) -> None:
    """Every concrete pyvlx update refreshes the restore cache.

    Otherwise a transient UNKNOWN after a mid-session reconnect would
    fall back to a stale value (the initial seed) rather than to the
    most recent known live value.
    """
    mock_window.position.position_percent = 30  # HA = 70
    mock_window.position.known = True
    mock_window.position.closed = False

    await _setup(hass, mock_config_entry)

    # Live update moves the cover to HA position 20 (device 80%).
    mock_window.position.position_percent = 80
    await update_callback_entity(hass, mock_window)

    # Now pyvlx transitions back to UNKNOWN.
    mock_window.position.known = False
    await update_callback_entity(hass, mock_window)

    state = hass.states.get("cover.test_window")
    assert state is not None
    # Cache must reflect the most recent live value, not the startup seed.
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 20


@pytest.mark.parametrize(
    ("entity_id", "part_attr"),
    [
        ("cover.test_dual_roller_shutter", "position"),
        ("cover.test_dual_roller_shutter_upper_shutter", "position_upper_curtain"),
        ("cover.test_dual_roller_shutter_lower_shutter", "position_lower_curtain"),
    ],
)
@pytest.mark.parametrize("mock_pyvlx", ["mock_dual_roller_shutter"], indirect=True)
async def test_dual_roller_shutter_parts_seed_from_persisted_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: AsyncMock,
    mock_dual_roller_shutter: AsyncMock,
    entity_id: str,
    part_attr: str,
) -> None:
    """Each dual-roller-shutter part restores from its own persisted attribute."""
    getattr(mock_dual_roller_shutter, part_attr).known = False

    mock_restore_cache(
        hass,
        [State(entity_id, STATE_OPEN, attributes={ATTR_CURRENT_POSITION: 60})],
    )

    await _setup(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 60
