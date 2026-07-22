"""Tests for the Edifier Infrared integration setup."""

import pytest

from homeassistant.components.edifier_infrared.const import (
    CONF_COMMAND_SET,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("old_model", "old_command_set", "expected_model", "expected_command_set"),
    [
        pytest.param(
            "R1700BT",
            "r1700bt",
            "R1700BT (pre-2017)",
            "r1700bt_pre_2017",
            id="r1700bt-to-pre-2017",
        ),
        pytest.param(
            "R1700BTs", "r1700bt", "R1700BTs", "r1700bts", id="r1700bts-family"
        ),
        pytest.param("R1280DB", "r1280db", "R1280DB", "r1280db", id="unchanged-model"),
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_edifier_code_to_command")
async def test_migrate_entry_v1_to_v2(
    hass: HomeAssistant,
    old_model: str,
    old_command_set: str,
    expected_model: str,
    expected_command_set: str,
) -> None:
    """Test v1 config entries are migrated to the split R1700BT command sets."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Edifier {old_model} via Test IR emitter",
        data={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_MODEL: old_model,
            CONF_COMMAND_SET: old_command_set,
        },
        unique_id=f"{old_command_set}_{EMITTER_ENTITY_ID}",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.data[CONF_MODEL] == expected_model
    assert entry.data[CONF_COMMAND_SET] == expected_command_set
    assert entry.unique_id == f"{expected_command_set}_{EMITTER_ENTITY_ID}"
