"""Test the Emby config flow."""

import pytest

from homeassistant.components.emby.const import DEFAULT_SSL_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from .const import TEST_API_KEY_VALUE, TEST_HOST_VALUE, TEST_PORT_VALUE, TEST_SSL_VALUE

from tests.common import MockConfigEntry


async def test_user_step_success(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test successful setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: TEST_API_KEY_VALUE,
            CONF_HOST: TEST_HOST_VALUE,
            CONF_PORT: TEST_PORT_VALUE,
            CONF_SSL: TEST_SSL_VALUE,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["context"]["unique_id"] == f"{TEST_HOST_VALUE}:{TEST_PORT_VALUE}"
    assert result["title"] == f"{TEST_HOST_VALUE}:{TEST_PORT_VALUE}"
    assert result["data"] == {
        CONF_API_KEY: TEST_API_KEY_VALUE,
        CONF_HOST: TEST_HOST_VALUE,
        CONF_PORT: TEST_PORT_VALUE,
        CONF_SSL: TEST_SSL_VALUE,
    }


async def test_already_configured(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Try (and fail) setting up a config entry when one already exists."""
    # Try to start the flow
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: TEST_API_KEY_VALUE,
            CONF_HOST: TEST_HOST_VALUE,
            CONF_PORT: TEST_PORT_VALUE,
            CONF_SSL: TEST_SSL_VALUE,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML media_player which is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    IMPORT_DATA = {
        "platform": DOMAIN,
        "api_key": TEST_API_KEY_VALUE,
        "host": TEST_HOST_VALUE,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["context"]["unique_id"] == f"{TEST_HOST_VALUE}:8096"
    assert result["title"] == f"{TEST_HOST_VALUE}:8096"
    assert result["data"] == {
        CONF_API_KEY: TEST_API_KEY_VALUE,
        CONF_HOST: TEST_HOST_VALUE,
        CONF_PORT: 8096,
        CONF_SSL: False,
    }


async def test_yaml_import_ssl(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML media_player which is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    IMPORT_DATA = {
        "platform": DOMAIN,
        "api_key": TEST_API_KEY_VALUE,
        "host": TEST_HOST_VALUE,
        "ssl": True,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["context"]["unique_id"] == f"{TEST_HOST_VALUE}:{DEFAULT_SSL_PORT}"
    assert result["title"] == f"{TEST_HOST_VALUE}:{DEFAULT_SSL_PORT}"
    assert result["data"] == {
        CONF_API_KEY: TEST_API_KEY_VALUE,
        CONF_HOST: TEST_HOST_VALUE,
        CONF_PORT: DEFAULT_SSL_PORT,
        CONF_SSL: True,
    }


async def test_failed_yaml_import_already_configured(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a YAML media_player which is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    mock_config_entry.add_to_hass(hass)
    IMPORT_DATA = {
        "platform": DOMAIN,
        "api_key": TEST_API_KEY_VALUE,
        "host": TEST_HOST_VALUE,
        "port": TEST_PORT_VALUE,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
