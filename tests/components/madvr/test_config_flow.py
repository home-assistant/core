"""Test the MadVR config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.madvr.config_flow import CannotConnect
from homeassistant.components.madvr.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG, MOCK_MAC


@pytest.fixture(name="mock_madvr")
def mock_madvr():
    """Mock the MadVR client."""
    with patch("homeassistant.components.madvr.config_flow.Madvr") as mock_madvr:
        mock_madvr.return_value.connected = True
        yield mock_madvr


async def test_user_form(hass: HomeAssistant, mock_madvr) -> None:
    """Test we get the user form and can set up the integration successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    mock_madvr.return_value.open_connection = MagicMock()
    mock_mac = MOCK_MAC

    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value=mock_mac,
    ):
        configFlowResult = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": MOCK_CONFIG[CONF_HOST],
                "port": MOCK_CONFIG[CONF_PORT],
            },
        )
        await hass.async_block_till_done()

    assert configFlowResult["type"] == FlowResultType.CREATE_ENTRY
    assert configFlowResult["title"] == DEFAULT_NAME
    assert configFlowResult["data"] == {
        "host": MOCK_CONFIG[CONF_HOST],
        "port": MOCK_CONFIG[CONF_PORT],
    }

    assert configFlowResult["result"].unique_id == mock_mac


async def test_user_form_cannot_connect(hass: HomeAssistant, mock_madvr) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_madvr.return_value.open_connection = MagicMock(side_effect=CannotConnect)
    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        side_effect=CannotConnect,
    ):
        errorFlowResult = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": MOCK_CONFIG[CONF_HOST],
                "port": MOCK_CONFIG[CONF_PORT],
            },
        )

    # Check that we're still on the form step after the error
    assert errorFlowResult["type"] == FlowResultType.FORM
    # Check that we're still on the user step
    assert errorFlowResult["step_id"] == "user"
    # Check that we have the correct error
    assert errorFlowResult["errors"] == {"base": "cannot_connect"}

    # Test that we can retry the connection
    mock_mac = MOCK_MAC
    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value=mock_mac,
    ):
        retryFlowResult = await hass.config_entries.flow.async_configure(
            errorFlowResult["flow_id"],
            {
                "host": MOCK_CONFIG[CONF_HOST],
                "port": MOCK_CONFIG[CONF_PORT],
            },
        )

    assert retryFlowResult["type"] == FlowResultType.CREATE_ENTRY
    assert retryFlowResult["title"] == DEFAULT_NAME
    assert retryFlowResult["data"] == {
        "host": MOCK_CONFIG[CONF_HOST],
        "port": MOCK_CONFIG[CONF_PORT],
    }
    assert retryFlowResult["result"].unique_id == mock_mac


async def test_user_form_no_mac(hass: HomeAssistant, mock_madvr) -> None:
    """Test we handle the case when no MAC is returned."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_madvr.return_value.open_connection = MagicMock()
    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value="",  # Simulating no MAC returned
    ):
        errorFlowResult = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": MOCK_CONFIG[CONF_HOST],
                "port": MOCK_CONFIG[CONF_PORT],
            },
        )
        await hass.async_block_till_done()

    assert errorFlowResult["type"] == FlowResultType.FORM
    assert errorFlowResult["step_id"] == "user"
    assert errorFlowResult["errors"] == {"base": "no_mac"}

    # Test that we can retry and succeed if a MAC is returned on the second attempt
    mock_mac = MOCK_MAC
    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value=mock_mac,
    ):
        retryResult = await hass.config_entries.flow.async_configure(
            errorFlowResult["flow_id"],
            {
                "host": MOCK_CONFIG[CONF_HOST],
                "port": MOCK_CONFIG[CONF_PORT],
            },
        )
        await hass.async_block_till_done()

    assert retryResult["type"] == FlowResultType.CREATE_ENTRY
    assert retryResult["title"] == DEFAULT_NAME
    assert retryResult["data"] == {
        "host": MOCK_CONFIG[CONF_HOST],
        "port": MOCK_CONFIG[CONF_PORT],
    }
    assert retryResult["result"].unique_id == mock_mac
