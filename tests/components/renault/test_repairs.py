"""Tests for Renault repairs."""

from collections.abc import Generator
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant.components.renault.const import DOMAIN, RenaultConfigurationKeys
from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import FORBIDDEN_EXCEPTION, MOCK_ACCOUNT_ID, MOCK_CONFIG, OTHER_ACCOUNT_ID

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

ISSUE_ID = "account_not_found_123456"

pytestmark = [
    pytest.mark.usefixtures(
        "patch_renault_account", "patch_get_api_accounts", "patch_get_vehicles"
    ),
    pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True),
    pytest.mark.parametrize("account_ids", [[OTHER_ACCOUNT_ID]]),
]


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", []):
        yield


async def _setup_with_account_not_found(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Load the entry, then fail setup because its account no longer exists."""
    assert await async_setup_component(hass, "repairs", {})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        side_effect=FORBIDDEN_EXCEPTION,
    ):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("title", "expected_title"),
    [
        pytest.param(MOCK_ACCOUNT_ID, OTHER_ACCOUNT_ID, id="default_title"),
        pytest.param("My car", "My car", id="custom_title"),
    ],
)
async def test_account_not_found_repair(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    config_entry: ConfigEntry,
    title: str,
    expected_title: str,
) -> None:
    """Test moving the entry to the new account of its vehicles."""
    hass.config_entries.async_update_entry(config_entry, title=title)
    await _setup_with_account_not_found(hass, config_entry)

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "account"

    result = await process_repair_fix_flow(
        client,
        result["flow_id"],
        json={RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID: OTHER_ACCOUNT_ID},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == OTHER_ACCOUNT_ID
    assert config_entry.title == expected_title
    assert (
        config_entry.data[RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID]
        == OTHER_ACCOUNT_ID
    )
    assert len(issue_registry.issues) == 0


async def test_account_not_found_repair_already_configured(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
) -> None:
    """Test the repair aborts when the new account already has an entry."""
    MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            **MOCK_CONFIG,
            RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID: OTHER_ACCOUNT_ID,
        },
        unique_id=OTHER_ACCOUNT_ID,
    ).add_to_hass(hass)
    await _setup_with_account_not_found(hass, config_entry)

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_new_account"


async def test_account_not_found_repair_cannot_connect(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
) -> None:
    """Test the repair aborts when the Renault servers can't be reached."""
    await _setup_with_account_not_found(hass, config_entry)

    client = await hass_client()
    with patch(
        "renault_api.renault_client.RenaultClient.get_api_accounts",
        side_effect=aiohttp.ClientConnectionError,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
