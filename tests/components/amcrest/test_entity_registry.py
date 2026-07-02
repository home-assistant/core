"""Integration-level tests for entity registry unique ID behaviour.

These tests exercise the full setup path (async_setup_component + platform
loading) and assert on hass.states / entity registry entries rather than on
internal entity attributes, following the documented HA testing approach.

The key regression being guarded: prior to this PR, serial numbers were not
persisted across restarts, so on a second HA start (with the camera offline)
entities got unique_id=None.  HA then tried to assign entity IDs based on
entity names, but the entity registry still held the IDs from the first run,
causing a _2 suffix to appear and the entity_id to change silently.
"""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.amcrest.switch import SWITCH_TYPES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import CAMERA_CONFIG, SERIAL_NUMBER, _MockAmcrestAPI

# Default camera name produced by the amcrest config schema when no `name` key
# is supplied in CAMERA_CONFIG.
_DEFAULT_CAMERA_NAME = "Amcrest Camera"


@pytest.mark.usefixtures("mock_event_monitor")
async def test_entities_registered_with_serial_unique_ids(
    hass: HomeAssistant,
    mock_store: MagicMock,
    mock_api: _MockAmcrestAPI,
) -> None:
    """After full setup, every entity is in the registry with a serial-based unique ID."""
    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_api
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    amcrest_entries = [
        entry for entry in registry.entities.values() if entry.platform == "amcrest"
    ]
    assert amcrest_entries, "Expected amcrest entities in the registry"
    for entry in amcrest_entries:
        assert entry.unique_id.startswith(SERIAL_NUMBER), (
            f"{entry.entity_id!r} has unique_id {entry.unique_id!r}; "
            f"expected prefix {SERIAL_NUMBER!r}"
        )


@pytest.mark.usefixtures("mock_event_monitor")
async def test_entity_ids_stable_across_restart(
    hass: HomeAssistant,
    mock_store: MagicMock,
    mock_api: _MockAmcrestAPI,
) -> None:
    """Entity IDs are reused without a _2 suffix when HA restarts with a stored serial.

    Sequence:
    1. Populate the entity registry with the switch entry that a previous HA run
       would have created (unique_id anchored to SERIAL_NUMBER).
    2. Re-run setup loading the serial from storage (simulating a restart).
    3. Verify the switch entity claims the pre-existing registry entry rather than
       generating a new entity_id with a _2 suffix.
    """
    registry = er.async_get(hass)
    switch_unique_id = f"{SERIAL_NUMBER}-{SWITCH_TYPES[0].key}-0"

    # Simulate the entity registry state left by a previous HA instance.
    # The suggested_object_id matches what amcrest would derive from the entity
    # name "Amcrest Camera Privacy Mode" (platform name + switch description name).
    prior_entry = registry.async_get_or_create(
        "switch",
        "amcrest",
        switch_unique_id,
        suggested_object_id="amcrest_camera_privacy_mode",
    )

    # Simulate restart: serial is already in storage from the previous run.
    mock_store.async_load.return_value = {
        "serial_numbers": {_DEFAULT_CAMERA_NAME: SERIAL_NUMBER}
    }

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_api
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)
        await hass.async_block_till_done()

    # The switch must reuse the pre-existing registry entry — same entity_id,
    # no _2 suffix, and no duplicate entry.
    reused_entry = registry.async_get(prior_entry.entity_id)
    assert reused_entry is not None, "Prior registry entry was unexpectedly removed"
    assert reused_entry.entity_id == prior_entry.entity_id

    switch_entries = [
        e
        for e in registry.entities.values()
        if e.platform == "amcrest" and e.domain == "switch"
    ]
    assert not any("_2" in e.entity_id for e in switch_entries), (
        f"Unexpected _2 suffix: {[e.entity_id for e in switch_entries]}"
    )
    assert len(switch_entries) == len(SWITCH_TYPES), (
        f"Expected {len(SWITCH_TYPES)} switch entries, got {len(switch_entries)}"
    )
