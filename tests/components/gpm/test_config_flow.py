"""Test the GPM config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.gpm._manager import IntegrationRepositoryManager
from homeassistant.components.gpm.const import CONF_UPDATE_STRATEGY, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigFlow
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
async def make_user_input(**kwargs):
    """Return a default user input, possibly overrides some keys."""

    def _make_user_input(**kwargs) -> dict[str, str]:
        return {
            CONF_URL: "https://github.com/user/awesome-component",
            CONF_TYPE: "integration",
            CONF_UPDATE_STRATEGY: "latest_tag",
            **kwargs,
        }

    return _make_user_input


@pytest.fixture
async def make_config_flow(hass: HomeAssistant):
    """Return a configured config flow."""

    async def _make_config_flow():
        config_flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert config_flow["type"] == FlowResultType.FORM
        assert config_flow["errors"] == {}
        return config_flow

    return _make_config_flow


async def test_integration(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_integration_manager: IntegrationRepositoryManager,
    make_config_flow,
    make_user_input,
) -> None:
    """Test we get the form."""
    config_flow = await make_config_flow()
    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"],
        make_user_input(),
    )
    await hass.async_block_till_done()
    mock_integration_manager.clone.assert_called_once()
    mock_integration_manager.checkout.assert_called_with("v1.0.0")
    mock_integration_manager.install.assert_called_once()

    assert config_flow["type"] == FlowResultType.CREATE_ENTRY
    assert config_flow["title"] == "awesome_component"
    assert config_flow["data"] == {
        CONF_URL: "https://github.com/user/awesome-component",
        CONF_TYPE: "integration",
        CONF_UPDATE_STRATEGY: "latest_tag",
    }
    mock_setup_entry.assert_called_once()


async def test_integration_invalid_url(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_integration_manager: IntegrationRepositoryManager,
    make_config_flow,
    make_user_input,
) -> None:
    """Test we handle invalid URL."""
    config_flow = await make_config_flow()
    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"],
        make_user_input(url="this-is-not-a-url"),
    )
    await hass.async_block_till_done()
    mock_integration_manager.clone.assert_not_called()

    # test recovery from URL validation error
    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"],
        make_user_input(),
    )
    assert config_flow["type"] == FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_called_once()


async def test_abort_on_duplicate_unique_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_integration_manager: IntegrationRepositoryManager,
    make_config_flow,
    make_user_input,
) -> None:
    """Test we abort on duplicate unique ID."""
    config_flow = await make_config_flow()
    config_flow = await hass.config_entries.flow.async_configure(
        config_flow["flow_id"],
        make_user_input(),
    )
    await hass.async_block_till_done()
    another_config_flow = await make_config_flow()
    another_config_flow = await hass.config_entries.flow.async_configure(
        another_config_flow["flow_id"],
        make_user_input(),
    )
    await hass.async_block_till_done()
    assert config_flow["flow_id"] != another_config_flow["flow_id"]
    assert another_config_flow["type"] == FlowResultType.ABORT
    assert another_config_flow["reason"] == "already_configured"
    mock_setup_entry.assert_called_once()
