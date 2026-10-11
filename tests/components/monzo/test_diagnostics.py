"""Tests for Monzo diagnostics."""

import json
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.monzo.const import CONF_CLOUDHOOK_URL
from homeassistant.core import HomeAssistant

from .conftest import (
    OWNER,
    TEST_ACCOUNTS,
    TEST_POTS,
    TITLE,
    USER_ID,
    WEBHOOK_ID,
    WEBHOOK_URL,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

CLOUDHOOK_URL = "https://hooks.nabu.casa/test-cloudhook"


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics and redaction."""
    joint_account = {
        "id": "acc_joint",
        "name": "Joint Account",
        "type": "uk_retail_joint",
        "owners": [OWNER, {"preferred_name": "Jake Martin"}],
        "balance": {
            "balance": 456,
            "total_balance": 654,
            "spend_today": -78,
            "currency": "GBP",
        },
    }
    unlinked_pot = {
        **TEST_POTS[0],
        "id": "pot_unlinked",
        "name": "Unlinked pot",
        "current_account_id": "acc_missing",
    }
    monzo.user_account.accounts.return_value = [*TEST_ACCOUNTS, joint_account]
    monzo.user_account.pots.return_value = [*TEST_POTS, unlinked_pot]
    polling_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        polling_config_entry,
        data={**polling_config_entry.data, CONF_CLOUDHOOK_URL: CLOUDHOOK_URL},
    )
    await hass.config_entries.async_setup(polling_config_entry.entry_id)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, polling_config_entry
    )

    assert result == snapshot(exclude=props("created_at", "modified_at"))
    serialized_result = json.dumps(result)
    assert TITLE not in serialized_result
    assert str(USER_ID) not in serialized_result
    assert OWNER["preferred_name"] not in serialized_result
    assert WEBHOOK_ID not in serialized_result
    assert WEBHOOK_URL not in serialized_result
    assert CLOUDHOOK_URL not in serialized_result
    assert "mock-access-token" not in serialized_result
    assert "mock-refresh-token" not in serialized_result
    assert "acc_curr" not in serialized_result
    assert "acc_flex" not in serialized_result
    assert "acc_joint" not in serialized_result
    assert "acc_missing" not in serialized_result
    assert "pot_savings" not in serialized_result
    assert "pot_unlinked" not in serialized_result
    assert "Current Account" not in serialized_result
    assert "Joint Account" not in serialized_result
    assert "Savings" not in serialized_result
    assert "Unlinked pot" not in serialized_result

    assert {account["type"] for account in result["coordinator"]["accounts"]} == {
        "uk_monzo_flex",
        "uk_retail",
        "uk_retail_joint",
    }
