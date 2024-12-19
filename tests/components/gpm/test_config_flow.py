"""Test the GPM config flow."""

from pathlib import Path
from unittest.mock import AsyncMock

from homeassistant.components.gpm._manager import (
    AlreadyClonedError,
    CloneError,
    IntegrationRepositoryManager,
    InvalidStructure,
    RepositoryType,
    ResourceRepositoryManager,
    UpdateStrategy,
)
from homeassistant.components.gpm.const import (
    CONF_DOWNLOAD_URL,
    CONF_UPDATE_STRATEGY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_async_step_install_integration(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test async_step_install for integration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert integration_manager.clone.await_count == 1
    assert integration_manager.checkout.await_count == 1
    assert integration_manager.install.await_count == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "awesome_component"
    assert result["data"] == {
        CONF_URL: "https://github.com/user/awesome-component",
        CONF_TYPE: "integration",
        CONF_UPDATE_STRATEGY: UpdateStrategy.LATEST_TAG,
    }
    assert mock_setup_entry.call_count == 1


async def test_async_step_user_integration_invalid_url(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test handling of invalid URL in async_step_user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "this-is-not-a-url"},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}
    assert integration_manager.clone.await_count == 0

    # test recovery from URL validation error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_setup_entry.call_count == 1


async def test_async_step_user_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test handling of duplicate unique_id in async_step_user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_setup_entry.call_count == 1
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert mock_setup_entry.call_count == 1


async def test_async_step_install_invalid_structure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test handling of GPMError exception in async_step_install."""
    integration_manager.get_latest_version.side_effect = InvalidStructure(
        "foobar", Path("foobar")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert integration_manager.clone.await_count == 1
    assert integration_manager.checkout.await_count == 0
    assert integration_manager.remove.await_count == 1
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_structure"
    assert mock_setup_entry.call_count == 0


async def test_async_step_install_already_cloned(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test handling of GPMError exception in async_step_install."""
    integration_manager.clone.side_effect = AlreadyClonedError(Path("foobar"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert integration_manager.clone.await_count == 1
    assert integration_manager.checkout.await_count == 0
    assert integration_manager.remove.await_count == 0
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "install_failed"
    assert mock_setup_entry.call_count == 0


async def test_async_step_install_failed(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test handling of unexpected exception in async_step_install."""
    integration_manager.clone.side_effect = CloneError("foobar", Path("foobar"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert integration_manager.clone.await_count == 1
    assert integration_manager.get_latest_version.await_count == 0
    assert integration_manager.remove.await_count == 1
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "install_failed"
    assert mock_setup_entry.call_count == 0


async def test_async_step_install_unexpected_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test handling of unexpected exception in async_step_install."""
    integration_manager.clone.side_effect = ValueError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://github.com/user/awesome-component"},
    )
    await hass.async_block_till_done()
    assert integration_manager.clone.await_count == 1
    assert integration_manager.get_latest_version.await_count == 0
    assert integration_manager.remove.await_count == 0
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"
    assert mock_setup_entry.call_count == 0


async def test_async_step_install_resource(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    resource_manager: ResourceRepositoryManager,
) -> None:
    """Test async_step_install for resource."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://github.com/user/awesome-card",
            CONF_TYPE: RepositoryType.RESOURCE,
        },
    )
    await hass.async_block_till_done()
    assert resource_manager.clone.await_count == 0
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOWNLOAD_URL: "https://github.com/user/awesome-card/releases/download/{{ version }}/bundle.js"
        },
    )
    await hass.async_block_till_done()
    assert resource_manager.clone.await_count == 1
    assert resource_manager.checkout.await_count == 1
    assert resource_manager.install.await_count == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "awesome_card"
    assert result["data"] == {
        CONF_URL: "https://github.com/user/awesome-card",
        CONF_TYPE: RepositoryType.RESOURCE,
        CONF_UPDATE_STRATEGY: UpdateStrategy.LATEST_TAG,
        CONF_DOWNLOAD_URL: "https://github.com/user/awesome-card/releases/download/{{ version }}/bundle.js",
    }
    assert mock_setup_entry.call_count == 1


async def test_async_step_resource_invalid_template(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    resource_manager: ResourceRepositoryManager,
) -> None:
    """Test handling of invalid template in async_step_resource."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://github.com/user/awesome-card",
            CONF_TYPE: RepositoryType.RESOURCE,
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOWNLOAD_URL: "https://{{% foobar %}}github.com/user/awesome-card/releases/download/version/bundle.js"
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_DOWNLOAD_URL: "invalid_template"}
    assert resource_manager.clone.await_count == 0

    # test recovery from template validation error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DOWNLOAD_URL: "https://example.com/bundle_{{version}}.js"},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_setup_entry.call_count == 1
