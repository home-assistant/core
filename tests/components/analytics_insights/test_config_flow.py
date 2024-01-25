"""Test the Homeassistant Analytics config flow."""
from unittest.mock import AsyncMock

from python_homeassistant_analytics import HomeassistantAnalyticsConnectionError

from homeassistant import config_entries
from homeassistant.components.analytics_insights.const import (
    CONF_TRACKED_INTEGRATIONS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_analytics_client: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRACKED_INTEGRATIONS: ["youtube"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Analytics Insights"
    assert result["data"] == {}
    assert result["options"] == {CONF_TRACKED_INTEGRATIONS: ["youtube"]}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_analytics_client: AsyncMock
) -> None:
    """Test we handle cannot connect error."""

    mock_analytics_client.get_integrations.side_effect = (
        HomeassistantAnalyticsConnectionError
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_TRACKED_INTEGRATIONS: ["youtube", "spotify"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
