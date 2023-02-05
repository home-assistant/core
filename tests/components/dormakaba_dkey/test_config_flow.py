"""Test the Dormakaba dKey config flow."""
from unittest.mock import patch

from bleak.exc import BleakError
from py_dormakaba_dkey import errors as dkey_errors
from py_dormakaba_dkey.models import AssociationData
import pytest

from homeassistant import config_entries
from homeassistant.components.dormakaba_dkey.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import DKEY_DISCOVERY_INFO


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test bluetooth step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "bluetooth_connect"
    assert result["progress_action"] == "wait_for_bluetooth_connect"

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.connect"
    ) as mock_connect, patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.disconnect"
    ) as mock_disconnect:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "associate"
    mock_connect.assert_awaited_once()
    mock_disconnect.assert_awaited_once()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.associate",
        return_value=AssociationData(b"1234", b"AABBCCDD"),
    ) as mock_associate, patch(
        "homeassistant.components.dormakaba_dkey.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"activation_code": "1234-1234"}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DKEY_DISCOVERY_INFO.name
    assert result["data"] == {
        CONF_ADDRESS: DKEY_DISCOVERY_INFO.address,
        "association_data": {"key_holder_id": "31323334", "secret": "4141424243434444"},
    }
    assert result["options"] == {}
    assert result["result"].unique_id == DKEY_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1
    mock_associate.assert_awaited_once_with("1234-1234")


@pytest.mark.parametrize("exc", (BleakError, Exception))
async def test_bluetooth_step_cannot_connect(hass: HomeAssistant, exc) -> None:
    """Test bluetooth step and we cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "bluetooth_connect"
    assert result["progress_action"] == "wait_for_bluetooth_connect"

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.connect",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "could_not_connect"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "could_not_connect"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "bluetooth_connect"
    assert result["progress_action"] == "wait_for_bluetooth_connect"


@pytest.mark.parametrize(
    "exc, error",
    (
        (dkey_errors.InvalidActivationCode, "invalid_code"),
        (dkey_errors.WrongActivationCode, "wrong_code"),
        (Exception, "unknown"),
    ),
)
async def test_bluetooth_step_cannot_associate(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth step and we cannot associate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "bluetooth_connect"
    assert result["progress_action"] == "wait_for_bluetooth_connect"

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.connect"
    ) as mock_connect:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "associate"
    mock_connect.assert_awaited_once()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.associate",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"activation_code": "1234-1234"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] == {"base": error}
