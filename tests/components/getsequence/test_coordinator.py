"""Tests for the SequenceDataUpdateCoordinator in the getsequence integration."""

from unittest.mock import AsyncMock

import aiohttp
from GetSequenceIoApiClient import SequenceApiError
import pytest

from homeassistant.components.getsequence.const import DOMAIN
from homeassistant.components.getsequence.coordinator import (
    SequenceDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_coordinator_investments_logging_branch(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test coordinator covers the 'if investments:' debug branch."""
    async with aiohttp.ClientSession() as session:
        config_entry = ConfigEntry(
            data={"access_token": "test_token"},
            discovery_keys={},
            domain=DOMAIN,
            entry_id="test_entry_id",
            minor_version=1,
            options={},
            pref_disable_new_entities=False,
            pref_disable_polling=False,
            source="user",
            state=None,
            subentries_data=None,
            title="Test",
            unique_id="test_unique_id",
            version=1,
        )
        coordinator = SequenceDataUpdateCoordinator(
            hass,
            config_entry,
            session,
            update_interval=None,
        )
        mock_accounts = {
            "data": {
                "accounts": [
                    {
                        "id": "inv1",
                        "name": "Investment 1",
                        "type": "Investment",
                        "balance": {"amountInDollars": 5000},
                    }
                ]
            }
        }
        coordinator.api.async_get_accounts = AsyncMock(return_value=mock_accounts)
        coordinator.api.get_pod_accounts = lambda data: []
        coordinator.api.get_income_source_accounts = lambda data: []
        coordinator.api.get_liability_accounts = lambda data, ids: []
        # Return a non-empty investments list to trigger the branch
        coordinator.api.get_investment_accounts = lambda data, ids: [
            {
                "id": "inv1",
                "name": "Investment 1",
                "type": "Investment",
            }
        ]
        coordinator.api.get_external_accounts = lambda data: []
        coordinator.api.get_uncategorized_external_accounts = (
            lambda data, l_ids, i_ids: []
        )
        coordinator.api.get_adjusted_total_balance = lambda data, l_ids, l_conf: 0
        coordinator.api.get_total_balance = lambda data: 0
        coordinator.api.get_pod_balance = lambda data: 0
        coordinator.api.get_configured_liability_balance = lambda data, ids: 0
        coordinator.api.get_configured_investment_balance = lambda data, ids: 0
        coordinator.api.get_balance_by_type = lambda data, typ: 0
        coordinator.api.get_uncategorized_external_balance = (
            lambda data, l_ids, i_ids: 0
        )
        coordinator.api.get_account_types_summary = lambda data: {}
        with caplog.at_level("DEBUG"):
            await coordinator._async_update_data()
        # Ensure the debug log for investments is present
        assert any("Investment accounts" in r for r in caplog.messages)


async def test_coordinator_sequence_api_error(hass: HomeAssistant) -> None:
    """Test SequenceApiError in coordinator._async_update_data."""
    async with aiohttp.ClientSession() as session:
        config_entry = ConfigEntry(
            data={"access_token": "test_token"},
            discovery_keys={},
            domain=DOMAIN,
            entry_id="test_entry_id",
            minor_version=1,
            options={},
            pref_disable_new_entities=False,
            pref_disable_polling=False,
            source="user",
            state=None,
            subentries_data=None,
            title="Test",
            unique_id="test_unique_id",
            version=1,
        )
        coordinator = SequenceDataUpdateCoordinator(
            hass,
            config_entry,
            session,
            update_interval=None,
        )
        # Patch the API client to raise SequenceApiError
        coordinator.api.async_get_accounts = AsyncMock(
            side_effect=SequenceApiError("fail")
        )
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_coordinator_successful_update(hass: HomeAssistant) -> None:
    """Test successful update returns processed data."""
    async with aiohttp.ClientSession() as session:
        config_entry = ConfigEntry(
            data={"access_token": "test_token"},
            discovery_keys={},
            domain=DOMAIN,
            entry_id="test_entry_id",
            minor_version=1,
            options={},
            pref_disable_new_entities=False,
            pref_disable_polling=False,
            source="user",
            state=None,
            subentries_data=None,
            title="Test",
            unique_id="test_unique_id",
            version=1,
        )
        coordinator = SequenceDataUpdateCoordinator(
            hass,
            config_entry,
            session,
            update_interval=None,
        )
        # Minimal mock response
        mock_accounts = {
            "data": {
                "accounts": [
                    {
                        "id": "1",
                        "name": "Test Pod",
                        "type": "Pod",
                        "balance": {"amountInDollars": 100},
                    },
                    {
                        "id": "2",
                        "name": "Test Income",
                        "type": "Income Source",
                        "balance": {"amountInDollars": 200},
                    },
                ]
            }
        }
        coordinator.api.async_get_accounts = AsyncMock(return_value=mock_accounts)
        # Patch all api methods to return simple values
        coordinator.api.get_pod_accounts = lambda data: [data["data"]["accounts"][0]]
        coordinator.api.get_income_source_accounts = lambda data: [
            data["data"]["accounts"][1]
        ]
        coordinator.api.get_liability_accounts = lambda data, ids: []
        coordinator.api.get_investment_accounts = lambda data, ids: []
        coordinator.api.get_external_accounts = lambda data: []
        coordinator.api.get_uncategorized_external_accounts = (
            lambda data, l_ids, i_ids: []
        )
        coordinator.api.get_adjusted_total_balance = lambda data, l_ids, l_conf: 300
        coordinator.api.get_total_balance = lambda data: 300
        coordinator.api.get_pod_balance = lambda data: 100
        coordinator.api.get_configured_liability_balance = lambda data, ids: 0
        coordinator.api.get_configured_investment_balance = lambda data, ids: 0
        coordinator.api.get_balance_by_type = lambda data, typ: 200
        coordinator.api.get_uncategorized_external_balance = (
            lambda data, l_ids, i_ids: 0
        )
        coordinator.api.get_account_types_summary = lambda data: {
            "Pod": 1,
            "Income Source": 1,
        }
        result = await coordinator._async_update_data()
        assert result["accounts"] == mock_accounts
        assert result["pods"][0]["id"] == "1"
        assert result["income_sources"][0]["id"] == "2"
        assert result["total_balance"] == 300


async def test_coordinator_options_handling(hass: HomeAssistant) -> None:
    """Test coordinator processes liability and investment options."""
    async with aiohttp.ClientSession() as session:
        options = {
            "liability_accounts": ["L1", "L2"],
            "investment_accounts": ["I1"],
            "liability_configured": True,
        }
        config_entry = ConfigEntry(
            data={"access_token": "test_token"},
            discovery_keys={},
            domain=DOMAIN,
            entry_id="test_entry_id",
            minor_version=1,
            options=options,
            pref_disable_new_entities=False,
            pref_disable_polling=False,
            source="user",
            state=None,
            subentries_data=None,
            title="Test",
            unique_id="test_unique_id",
            version=1,
        )
        coordinator = SequenceDataUpdateCoordinator(
            hass,
            config_entry,
            session,
            update_interval=None,
        )
        mock_accounts = {"data": {"accounts": []}}
        coordinator.api.async_get_accounts = AsyncMock(return_value=mock_accounts)
        coordinator.api.get_pod_accounts = lambda data: []
        coordinator.api.get_income_source_accounts = lambda data: []
        coordinator.api.get_liability_accounts = lambda data, ids: [
            {"id": id_, "name": f"Liability {id_}", "type": "Liability"} for id_ in ids
        ]
        coordinator.api.get_investment_accounts = lambda data, ids: [
            {"id": id_, "name": f"Investment {id_}", "type": "Investment"}
            for id_ in ids
        ]
        coordinator.api.get_external_accounts = lambda data: []
        coordinator.api.get_uncategorized_external_accounts = (
            lambda data, l_ids, i_ids: []
        )
        coordinator.api.get_adjusted_total_balance = lambda data, l_ids, l_conf: 0
        coordinator.api.get_total_balance = lambda data: 0
        coordinator.api.get_pod_balance = lambda data: 0
        coordinator.api.get_configured_liability_balance = lambda data, ids: len(ids)
        coordinator.api.get_configured_investment_balance = lambda data, ids: len(ids)
        coordinator.api.get_balance_by_type = lambda data, typ: 0
        coordinator.api.get_uncategorized_external_balance = (
            lambda data, l_ids, i_ids: 0
        )
        coordinator.api.get_account_types_summary = lambda data: {}
        result = await coordinator._async_update_data()
    assert [liab["id"] for liab in result["liabilities"]] == ["L1", "L2"]
    assert [inv["id"] for inv in result["investments"]] == ["I1"]
    assert result["liability_balance"] == 2
    assert result["investment_balance"] == 1
