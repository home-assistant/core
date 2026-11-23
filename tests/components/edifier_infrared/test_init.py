"""Tests for the Edifier Infrared integration setup."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID

from homeassistant.components.edifier_infrared.const import (
    CONF_COMMAND_SET,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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
        pytest.param("RC80B", "r1700bt", "RC80B", "rc80b", id="rc80b-split"),
        pytest.param("RC31A", "s360db", "RC31A", "r2600", id="rc31a-split"),
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_edifier_code_to_command")
async def test_migrate_entry_from_v1(
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
    assert entry.version == 4
    assert entry.data[CONF_MODEL] == expected_model
    assert entry.data[CONF_COMMAND_SET] == expected_command_set
    assert entry.unique_id == f"{expected_command_set}_{EMITTER_ENTITY_ID}"


@pytest.mark.parametrize(
    ("model", "old_command_set", "expected_command_set"),
    [
        pytest.param("R2000DB", "r1280db", "r2000db", id="r2000db-split"),
        pytest.param("R2730DB", "r1280db", "r2730db", id="r2730db-split"),
        pytest.param("RC10D1", "r1280db", "r2730db", id="rc10d1-split"),
        pytest.param("RC80B", "r1700bts", "rc80b", id="rc80b-split"),
        pytest.param("RC31A", "s360db", "r2600", id="rc31a-split"),
        pytest.param("R1280DB", "r1280db", "r1280db", id="unchanged-model"),
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_edifier_code_to_command")
async def test_migrate_entry_from_v2(
    hass: HomeAssistant,
    model: str,
    old_command_set: str,
    expected_command_set: str,
) -> None:
    """Test v2 config entries are migrated to the split R2000DB command set."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Edifier {model} via Test IR emitter",
        data={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_MODEL: model,
            CONF_COMMAND_SET: old_command_set,
        },
        unique_id=f"{old_command_set}_{EMITTER_ENTITY_ID}",
        version=2,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 4
    assert entry.data[CONF_MODEL] == model
    assert entry.data[CONF_COMMAND_SET] == expected_command_set
    assert entry.unique_id == f"{expected_command_set}_{EMITTER_ENTITY_ID}"


@pytest.mark.parametrize(
    ("model", "old_command_set", "expected_command_set"),
    [
        pytest.param("RC80B", "r1700bts", "rc80b", id="rc80b-split"),
        pytest.param("RC31A", "s360db", "r2600", id="rc31a-split"),
        pytest.param("R1700BTs", "r1700bts", "r1700bts", id="unchanged-model"),
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_edifier_code_to_command")
async def test_migrate_entry_from_v3(
    hass: HomeAssistant,
    model: str,
    old_command_set: str,
    expected_command_set: str,
) -> None:
    """Test v3 config entries are migrated to the split RC80B and R2600 command sets."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Edifier {model} via Test IR emitter",
        data={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_MODEL: model,
            CONF_COMMAND_SET: old_command_set,
        },
        unique_id=f"{old_command_set}_{EMITTER_ENTITY_ID}",
        version=3,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 4
    assert entry.data[CONF_MODEL] == model
    assert entry.data[CONF_COMMAND_SET] == expected_command_set
    assert entry.unique_id == f"{expected_command_set}_{EMITTER_ENTITY_ID}"


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize(
    ("model", "old_command_set", "old_keys", "expected_keys"),
    [
        pytest.param(
            "RC80B",
            "r1700bts",
            ["bluetooth", "line_1", "line_2"],
            {"bluetooth": "bluetooth", "opt_coax": "line_1", "line_1_2": "line_2"},
            id="rc80b-renames-buttons",
        ),
        pytest.param(
            "RC31A",
            "s360db",
            ["bluetooth", "optical", "coax", "pc", "aux"],
            {"pc": "pc", "aux": "aux"},
            id="rc31a-removes-buttons",
        ),
    ],
)
async def test_migrate_entry_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    version: int,
    model: str,
    old_command_set: str,
    old_keys: list[str],
    expected_keys: dict[str, str],
) -> None:
    """Test migration keeps or removes button entities for the new command set."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Edifier {model} via Test IR emitter",
        data={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_MODEL: model,
            CONF_COMMAND_SET: old_command_set,
        },
        unique_id=f"{old_command_set}_{EMITTER_ENTITY_ID}",
        version=version,
    )
    entry.add_to_hass(hass)
    old_entity_ids = {
        key: entity_registry.async_get_or_create(
            Platform.BUTTON,
            DOMAIN,
            f"{entry.entry_id}_{key}",
            config_entry=entry,
        ).entity_id
        for key in old_keys
    }

    with patch("homeassistant.components.edifier_infrared.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 4
    assert {
        entity_entry.unique_id: entity_entry.entity_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
    } == {
        f"{entry.entry_id}_{new_key}": old_entity_ids[old_key]
        for new_key, old_key in expected_keys.items()
    }
