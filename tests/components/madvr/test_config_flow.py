"""Test the MadVR config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.madvr.config_flow import CannotConnect
from homeassistant.components.madvr.const import DEFAULT_NAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(name="mock_madvr")
def mock_madvr():
    """Mock the MadVR client."""
    with patch("homeassistant.components.madvr.config_flow.Madvr") as mock_madvr:
        yield mock_madvr


async def test_user_form(hass: HomeAssistant, mock_madvr) -> None:
    """Test we get the user form and can set up the integration successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    mock_madvr.return_value.open_connection = MagicMock()
    mock_madvr.return_value.connected.return_value = True
    mock_mac = "00:11:22:33:44:55"

    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value=mock_mac,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.100",
                "port": 44077,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_NAME
    assert result2["data"] == {
        "host": "192.168.1.100",
        "port": 44077,
        "mac": mock_mac,
    }


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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.100",
                "port": 44077,
            },
        )

    # Check that we're still on the form step after the error
    assert result2["type"] == FlowResultType.FORM
    # Check that we're still on the user step
    assert result2["step_id"] == "user"
    # Check that we have the correct error
    assert result2["errors"] == {"base": "cannot_connect"}

    # Test that we can retry the connection
    mock_mac = "00:11:22:33:44:55"
    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value=mock_mac,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "host": "192.168.1.100",
                "port": 44077,
            },
        )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == DEFAULT_NAME
    assert result3["data"] == {
        "host": "192.168.1.100",
        "port": 44077,
        "mac": mock_mac,
    }


async def test_user_form_no_mac(hass: HomeAssistant, mock_madvr) -> None:
    """Test we can set up the integration even if no MAC is returned."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_madvr.return_value.open_connection = MagicMock()
    mock_madvr.return_value.connected.return_value = True

    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value="",  # Simulating no MAC returned
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.100",
                "port": 44077,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_NAME
    assert result2["data"] == {
        "host": "192.168.1.100",
        "port": 44077,
        "mac": "",  # Empty string for MAC
    }
