"""Tests migrations for Control4 integration."""

import pytest

from homeassistant.components.control4.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MOCK_CONTROLLER_UNIQUE_ID, MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return []


@pytest.mark.parametrize("scan_interval", [UPDATE_INTERVAL, None])
@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_migrate_entry_removes_default_scan_interval(
    hass: HomeAssistant,
    scan_interval: int | None,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test migrating an older entry removes the default scan interval option."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Controller",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            "controller_unique_id": MOCK_CONTROLLER_UNIQUE_ID,
        },
        unique_id="00:aa:00:aa:00:aa",
        options={CONF_SCAN_INTERVAL: scan_interval},
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "repairs", {})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert CONF_SCAN_INTERVAL not in config_entry.options
    assert config_entry.minor_version == 2

    assert not issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"user_configurable_polling_removed_{config_entry.entry_id}",
    )


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_repair_flow_removes_custom_scan_interval(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a custom scan interval creates an issue and a repair removes it."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Controller",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            "controller_unique_id": MOCK_CONTROLLER_UNIQUE_ID,
        },
        unique_id="00:aa:00:aa:00:aa",
        options={CONF_SCAN_INTERVAL: 1312},
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "repairs", {})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert CONF_SCAN_INTERVAL in config_entry.options
    assert config_entry.minor_version == 1

    assert (
        issue := issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"user_configurable_polling_removed_{config_entry.entry_id}",
        )
    )

    assert issue.data == {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id}
    assert issue.translation_key == "user_configurable_polling_removed"
    assert issue.translation_placeholders == {
        "custom_interval": "1312",
        "default_interval": "5",
        "update_entity": "`homeassistant.update_entity`",
    }

    client = await hass_client()
    result = await start_repair_fix_flow(
        client, DOMAIN, f"user_configurable_polling_removed_{config_entry.entry_id}"
    )

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"

    assert CONF_SCAN_INTERVAL not in config_entry.options
    assert config_entry.minor_version == 2


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_remove_entry_removes_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test removing a config entry also removes a repair issue."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Controller",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            "controller_unique_id": MOCK_CONTROLLER_UNIQUE_ID,
        },
        unique_id="00:aa:00:aa:00:aa",
        options={CONF_SCAN_INTERVAL: 1312},
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "repairs", {})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert CONF_SCAN_INTERVAL in config_entry.options
    assert config_entry.minor_version == 1

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"user_configurable_polling_removed_{config_entry.entry_id}",
    )

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"user_configurable_polling_removed_{config_entry.entry_id}",
    )
