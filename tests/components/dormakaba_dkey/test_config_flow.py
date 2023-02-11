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

from tests.common import MockConfigEntry


async def test_user_step(hass: HomeAssistant) -> None:
    """Test user step when there is a discovery flow."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_additional_devices_found"
    return


async def test_user_step_no_discovery_flow(hass: HomeAssistant) -> None:
    """Test user step with no discovery flows."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    return


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

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
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


async def test_bluetooth_step_already_configured(hass: HomeAssistant) -> None:
    """Test bluetooth step success path."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DKEY_DISCOVERY_INFO.address)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_step_already_in_progress(hass):
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    "exc, error",
    (
        (BleakError, "cannot_connect"),
        (Exception, "unknown"),
    ),
)
async def test_bluetooth_step_cannot_connect(hass: HomeAssistant, exc, error) -> None:
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
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.parametrize(
    "exc, error",
    (
        (dkey_errors.InvalidActivationCode, "invalid_code"),
        (dkey_errors.WrongActivationCode, "wrong_code"),
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


async def test_unignore_flow(hass: HomeAssistant) -> None:
    """Test a config flow started by unignoring a device."""
    # Create ignored entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IGNORE},
        data={
            "unique_id": DKEY_DISCOVERY_INFO.address,
            "title": DKEY_DISCOVERY_INFO.name,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["context"]["unique_id"] == DKEY_DISCOVERY_INFO.address

    # Unignore and expect rediscover call to bluetooth
    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_rediscover_address",
    ) as rediscover_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_UNIGNORE},
            data={"unique_id": DKEY_DISCOVERY_INFO.address},
        )
    rediscover_mock.assert_called_once_with(hass, DKEY_DISCOVERY_INFO.address)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
