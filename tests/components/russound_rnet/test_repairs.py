"""Test repairs for the Russound RNET integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.russound_rnet.const import (
    CONF_MODEL,
    CONF_SOURCES,
    CONF_ZONES,
    DOMAIN,
    TYPE_TCP,
)
from homeassistant.components.russound_rnet.repairs import (
    ISSUE_DEPRECATED_YAML,
    ISSUE_YAML_IMPORT,
    async_create_deprecated_yaml_issue,
    async_create_yaml_import_issue,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


async def test_yaml_import_repair_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the full YAML import repair flow: model → sources → zones → entry."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(hass, DOMAIN, {})

    yaml_config = {
        CONF_HOST: "192.168.1.100",
        CONF_NAME: "Russound",
        CONF_PORT: 9999,
        "zones": {1: {CONF_NAME: "Kitchen"}, 2: {CONF_NAME: "Living Room"}},
        "sources": [
            {CONF_NAME: "Sonos"},
            {CONF_NAME: "TV"},
        ],
    }
    async_create_yaml_import_issue(hass, yaml_config)

    issue_reg = ir.async_get(hass)
    assert len(issue_reg.issues) == 1
    issue = list(issue_reg.issues.values())[0]
    assert issue.issue_id == ISSUE_YAML_IMPORT
    assert issue.is_fixable is True

    await async_process_repairs_platforms(hass)
    client = await hass_client()

    # Start the fix flow — init validates connection, then shows confirm
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_YAML_IMPORT)
    assert data["step_id"] == "confirm"
    flow_id = data["flow_id"]

    # Submit confirm to proceed to model selection
    data = await process_repair_fix_flow(client, flow_id, {})
    assert data["step_id"] == "model"

    # Select model (CAS44 has 4 sources, 4 zones)
    data = await process_repair_fix_flow(client, flow_id, {CONF_MODEL: "cas44"})
    assert data["step_id"] == "sources"

    # Confirm sources (pre-filled from YAML)
    source_input = {
        "source_1": "Sonos",
        "source_2": "TV",
        "source_3": "",
        "source_4": "",
    }
    data = await process_repair_fix_flow(client, flow_id, source_input)
    assert data["step_id"] == "zones"

    # Confirm zones (pre-filled from YAML)
    zone_input = {
        "zone_1_1": "Kitchen",
        "zone_1_2": "Living Room",
        "zone_1_3": "",
        "zone_1_4": "",
    }
    data = await process_repair_fix_flow(client, flow_id, zone_input)
    assert data["type"] == "create_entry"

    # Verify config entry was created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.data[CONF_TYPE] == TYPE_TCP
    assert entry.data[CONF_HOST] == "192.168.1.100"
    assert entry.data[CONF_PORT] == 9999
    assert entry.data[CONF_MODEL] == "cas44"
    assert entry.data[CONF_SOURCES] == {"1": "Sonos", "2": "TV"}
    assert entry.data[CONF_ZONES] == {"1_1": "Kitchen", "1_2": "Living Room"}

    # Verify the import issue was deleted
    issue_reg = ir.async_get(hass)
    assert not issue_reg.async_get_issue(DOMAIN, ISSUE_YAML_IMPORT)


async def test_yaml_import_repair_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test repair flow aborts when device is unreachable."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(hass, DOMAIN, {})

    yaml_config = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 9999,
        "zones": {1: {CONF_NAME: "Kitchen"}},
        "sources": [{CONF_NAME: "Sonos"}],
    }
    async_create_yaml_import_issue(hass, yaml_config)

    mock_russound_client.connect.side_effect = TimeoutError

    await async_process_repairs_platforms(hass)
    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_YAML_IMPORT)
    assert data["type"] == "abort"
    assert data["reason"] == "cannot_connect"


async def test_deprecated_yaml_issue_created(
    hass: HomeAssistant,
) -> None:
    """Test deprecated YAML issue is non-fixable."""
    async_create_deprecated_yaml_issue(hass)

    issue_reg = ir.async_get(hass)
    assert len(issue_reg.issues) == 1
    issue = list(issue_reg.issues.values())[0]
    assert issue.issue_id == ISSUE_DEPRECATED_YAML
    assert issue.is_fixable is False


async def test_yaml_setup_platform_creates_import_issue(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test async_setup_platform creates fixable import issue when no config entry."""
    assert await async_setup_component(
        hass,
        "media_player",
        {
            "media_player": {
                "platform": "russound_rnet",
                "host": "192.168.1.100",
                "name": "Russound",
                "port": 9999,
                "zones": {1: {"name": "Kitchen"}},
                "sources": [{"name": "Sonos"}],
            }
        },
    )
    await hass.async_block_till_done()

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, ISSUE_YAML_IMPORT)


async def test_yaml_setup_platform_creates_deprecated_issue_when_entry_exists(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_platform creates deprecated issue when entry already exists."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        "media_player",
        {
            "media_player": {
                "platform": "russound_rnet",
                "host": "192.168.1.100",
                "name": "Russound",
                "port": 9999,
                "zones": {1: {"name": "Kitchen"}},
                "sources": [{"name": "Sonos"}],
            }
        },
    )
    await hass.async_block_till_done()

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, ISSUE_DEPRECATED_YAML)
    assert not issue_reg.async_get_issue(DOMAIN, ISSUE_YAML_IMPORT)
