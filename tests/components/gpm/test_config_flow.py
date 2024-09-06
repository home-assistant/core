"""Test the GPM config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.gpm._manager import IntegrationRepositoryManager
from homeassistant.components.gpm.const import CONF_UPDATE_STRATEGY, DOMAIN
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_integration(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_manager: IntegrationRepositoryManager,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://github.com/user/awesome-component",
            CONF_TYPE: "integration",
            CONF_UPDATE_STRATEGY: "latest_tag",
        },
    )
    await hass.async_block_till_done()
    mock_manager.clone.assert_called_once()
    mock_manager.checkout.assert_called_with("v1.0.0")
    mock_manager.install.assert_called_once()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "awesome_component"
    assert result["data"] == {
        CONF_URL: "https://github.com/user/awesome-component",
        CONF_TYPE: "integration",
        CONF_UPDATE_STRATEGY: "latest_tag",
    }
    mock_setup_entry.assert_called_once()
