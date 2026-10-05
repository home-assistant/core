"""Tests for the Hydro-Québec Peak Events config flow."""

from unittest.mock import AsyncMock, MagicMock

from hydropeak_opendata import OpenDataConnectionError

from homeassistant.components.hydroquebec_peak.const import CONF_OFFER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_OFFER

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full happy path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OFFER: TEST_OFFER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_OFFER
    assert result["data"] == {CONF_OFFER: TEST_OFFER}
    assert result["result"].unique_id == TEST_OFFER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test configuring the same offer twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OFFER: TEST_OFFER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cannot_connect(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test the flow aborts when the offer list cannot be fetched."""
    mock_client.get_offer_labels.side_effect = OpenDataConnectionError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
