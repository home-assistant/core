"""Test the MadVR config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.madvr import DOMAIN
from homeassistant.components.madvr.config_flow import CannotConnect
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

    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test MadVR",
                "host": "192.168.1.100",
                "mac": "00:11:22:33:44:55",
                "port": 44077,
                "keep_power_on": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test MadVR"
    assert result2["data"] == {
        "name": "Test MadVR",
        "host": "192.168.1.100",
        "mac": "00:11:22:33:44:55",
        "port": 44077,
        "keep_power_on": False,
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
                "name": "Test MadVR",
                "host": "192.168.1.100",
                "mac": "00:11:22:33:44:55",
                "port": 44077,
                "keep_power_on": False,
            },
        )

    # Check that we're still on the form step after the error
    assert result2["type"] == FlowResultType.FORM
    # Check that we're still on the user step
    assert result2["step_id"] == "user"
    # Check that we have the correct error
    assert result2["errors"] == {"base": "cannot_connect"}

    # Test that we can retry the connection
    with patch(
        "homeassistant.components.madvr.config_flow.MadVRConfigFlow._test_connection",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "name": "Test MadVR",
                "host": "192.168.1.100",
                "mac": "00:11:22:33:44:55",
                "port": 44077,
                "keep_power_on": False,
            },
        )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Test MadVR"
    assert result3["data"] == {
        "name": "Test MadVR",
        "host": "192.168.1.100",
        "mac": "00:11:22:33:44:55",
        "port": 44077,
        "keep_power_on": False,
    }
