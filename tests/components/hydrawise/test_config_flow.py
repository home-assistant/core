"""Test the Hydrawise config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from pydrawise.schema import User
import pytest

from homeassistant import config_entries
from homeassistant.components.hydrawise.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pydrawise: AsyncMock,
    user: User,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "abc123"}
    )
    mock_pydrawise.get_user.return_value = user
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Hydrawise"
    assert result2["data"] == {"api_key": "abc123"}
    assert len(mock_setup_entry.mock_calls) == 1
    mock_pydrawise.get_user.assert_called_once_with(fetch_zones=False)


async def test_form_api_error(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = ClientError("XXX")

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {"api_key": "abc123"}
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result2["type"] == FlowResultType.CREATE_ENTRY


async def test_form_connect_timeout(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = TimeoutError
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {"api_key": "abc123"}
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result2["type"] == FlowResultType.CREATE_ENTRY


async def test_flow_import_success(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test that we can import a YAML config."""
    mock_pydrawise.get_user.return_value = User
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "__api_key__",
            CONF_SCAN_INTERVAL: 120,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hydrawise"
    assert result["data"] == {
        CONF_API_KEY: "__api_key__",
    }

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_hydrawise"
    )
    assert issue.translation_key == "deprecated_yaml"


async def test_flow_import_api_error(
    hass: HomeAssistant, mock_pydrawise: AsyncMock
) -> None:
    """Test that we handle API errors on YAML import."""
    mock_pydrawise.get_user.side_effect = ClientError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "__api_key__",
            CONF_SCAN_INTERVAL: 120,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue.translation_key == "deprecated_yaml_import_issue"


async def test_flow_import_connect_timeout(
    hass: HomeAssistant, mock_pydrawise: AsyncMock
) -> None:
    """Test that we handle connection timeouts on YAML import."""
    mock_pydrawise.get_user.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "__api_key__",
            CONF_SCAN_INTERVAL: 120,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout_connect"

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_timeout_connect"
    )
    assert issue.translation_key == "deprecated_yaml_import_issue"


async def test_flow_import_already_imported(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test that we can handle a YAML config already imported."""
    mock_config_entry = MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "__api_key__",
        },
        unique_id="hydrawise-12345",
    )
    mock_config_entry.add_to_hass(hass)

    mock_pydrawise.get_user.return_value = user

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "__api_key__",
            CONF_SCAN_INTERVAL: 120,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_hydrawise"
    )
    assert issue.translation_key == "deprecated_yaml"
