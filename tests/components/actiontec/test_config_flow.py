"""Tests for the Actiontec config flow."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.actiontec.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG, MOCK_HOST

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_get_actiontec_data")
async def test_user_flow_success(
    hass: HomeAssistant,
) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_get_actiontec_data: MagicMock,
) -> None:
    """Test the user flow shows an error on connection failure."""
    mock_get_actiontec_data.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_get_actiontec_data")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_get_actiontec_data")
async def test_import_flow(
    hass: HomeAssistant,
) -> None:
    """Test a successful import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG


@pytest.mark.usefixtures("mock_setup_entry", "mock_get_actiontec_data")
async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the import flow aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_cannot_connect(
    hass: HomeAssistant,
    mock_get_actiontec_data: MagicMock,
) -> None:
    """Test the import flow aborts on connection failure."""
    mock_get_actiontec_data.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
