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
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from . import DKEY_DISCOVERY_INFO, NOT_DKEY_DISCOVERY_INFO

from tests.common import MockConfigEntry


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test user step success path."""
    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_discovered_service_info",
        return_value=[NOT_DKEY_DISCOVERY_INFO, DKEY_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: DKEY_DISCOVERY_INFO.address,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    await _test_common_success(hass, result)


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test user step with no devices found."""
    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_discovered_service_info",
        return_value=[NOT_DKEY_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_no_new_devices_found(hass: HomeAssistant) -> None:
    """Test user step with only existing devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: DKEY_DISCOVERY_INFO.address,
        },
        unique_id=DKEY_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_discovered_service_info",
        return_value=[DKEY_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_device_added_between_steps_1(hass: HomeAssistant) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_discovered_service_info",
        return_value=[DKEY_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DKEY_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": DKEY_DISCOVERY_INFO.address},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant,
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_discovered_service_info",
        return_value=[DKEY_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: DKEY_DISCOVERY_INFO.address,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    await _test_common_success(hass, result)

    # Verify the discovery flow was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test bluetooth step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    await _test_common_success(hass, result)


async def _test_common_success(hass: HomeAssistant, result: FlowResult) -> None:
    """Test bluetooth and user flow success paths."""

    with (
        patch(
            "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.associate",
            return_value=AssociationData(b"1234", b"AABBCCDD"),
        ) as mock_associate,
        patch(
            "homeassistant.components.dormakaba_dkey.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"activation_code": "1234-1234"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_step_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (BleakError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_bluetooth_step_cannot_connect(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth step and we cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.associate",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"activation_code": "1234-1234"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (dkey_errors.InvalidActivationCode, "invalid_code"),
        (dkey_errors.WrongActivationCode, "wrong_code"),
    ],
)
async def test_bluetooth_step_cannot_associate(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth step and we cannot associate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DKEY_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.associate",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"activation_code": "1234-1234"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] == {"base": error}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DKEY_DISCOVERY_INFO.address,
        data={"address": DKEY_DISCOVERY_INFO.address},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_last_service_info",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "no_longer_in_range"}

    with patch(
        "homeassistant.components.dormakaba_dkey.config_flow.async_last_service_info",
        return_value=DKEY_DISCOVERY_INFO,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "associate"
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.dormakaba_dkey.config_flow.DKEYLock.associate",
            return_value=AssociationData(b"1234", b"AABBCCDD"),
        ) as mock_associate,
        patch(
            "homeassistant.components.dormakaba_dkey.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"activation_code": "1234-1234"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_ADDRESS: DKEY_DISCOVERY_INFO.address,
        "association_data": {"key_holder_id": "31323334", "secret": "4141424243434444"},
    }
    mock_associate.assert_awaited_once_with("1234-1234")
