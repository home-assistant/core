"""Tests for the Hydro-Québec Peak Events config flow."""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hydropeak_opendata import OpenDataConnectionError, Sector
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hydroquebec_peak.const import CONF_OFFER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_OFFER


@pytest.mark.freeze_time("2026-01-08 12:00:00+00:00")
@pytest.mark.parametrize(
    ("step_id", "sector"),
    [
        pytest.param("residential", Sector.RESIDENTIAL, id="residential"),
        pytest.param("business", Sector.BUSINESS, id="business"),
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_setup_entry: AsyncMock,
    step_id: str,
    sector: Sector,
) -> None:
    """Test the full happy path for each customer type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    mock_client.get_sector_offers.assert_called_once_with(sector, date(2026, 1, 8))

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OFFER: TEST_OFFER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_OFFER
    assert result["data"] == {CONF_OFFER: TEST_OFFER}
    assert result["result"].unique_id == TEST_OFFER
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuring the same offer twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "residential"}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OFFER: TEST_OFFER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("mock_behavior", "reason"),
    [
        pytest.param(
            {"side_effect": OpenDataConnectionError("boom")},
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param({"return_value": ()}, "no_offers", id="no_offers"),
    ],
)
async def test_offer_list_unavailable(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_behavior: dict[str, Any],
    reason: str,
) -> None:
    """Test the flow aborts when there is no offer list to pick from."""
    mock_client.get_sector_offers.configure_mock(**mock_behavior)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "residential"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
