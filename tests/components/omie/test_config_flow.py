"""Test the OMIE - Spain and Portugal electricity prices config flow."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.omie.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import spot_price_fetcher

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_pyomie")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "OMIE"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant, mock_pyomie: MagicMock) -> None:
    """Test we handle connection error."""
    mock_pyomie.spot_price.side_effect = aiohttp.ClientError("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Fix the error and retry
    mock_pyomie.spot_price.side_effect = spot_price_fetcher({})
    result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_setup(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already set up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert len(mock_setup_entry.mock_calls) == 0
