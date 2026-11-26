"""Test the Schlage config flow."""

from unittest.mock import AsyncMock, Mock

from pyschlage.exceptions import Error as PyschlageError, NotAuthorizedError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.schlage.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import MockSchlageConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def _bluetooth_discovery(address: str = "AA:BB:CC:DD:EE:FF") -> BluetoothServiceInfo:
    """Return an advertisement as sent by a Schlage Encode."""
    return BluetoothServiceInfo(
        name="SCHLAGE00112233",
        address=address,
        rssi=-60,
        manufacturer_data={
            315: bytes.fromhex("01000902010049aabbccddeeffb5000000"),
        },
        service_data={},
        service_uuids=[],
        source="local",
    )


@pytest.mark.parametrize(
    "username",
    [
        "test-username",
        "TEST-USERNAME",
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyschlage_auth: Mock,
    username: str,
) -> None:
    """Test the full user flow, including that the username is normalized."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": username,
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    assert result2["result"].unique_id == "abc123"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test we abort if the account is already configured."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert init_result["type"] is FlowResultType.FORM
    assert init_result["errors"] == {}

    create_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert create_result["type"] is FlowResultType.ABORT
    assert create_result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(NotAuthorizedError, "invalid_auth", id="invalid_auth"),
        pytest.param(PyschlageError, "unknown", id="unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_pyschlage_auth: Mock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test we handle errors and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pyschlage_auth.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_pyschlage_auth.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure(
    hass: HomeAssistant,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test changing the email address and password of an account."""
    result = await mock_added_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "New@asdf.com", "password": "new-password"},
    )

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_added_config_entry.unique_id == "abc123"
    assert mock_added_config_entry.data == {
        "username": "new@asdf.com",
        "password": "new-password",
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(NotAuthorizedError, "invalid_auth", id="invalid_auth"),
        pytest.param(PyschlageError, "unknown", id="unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test the reconfigure flow handles errors and recovers."""
    result = await mock_added_config_entry.start_reconfigure_flow(hass)

    mock_pyschlage_auth.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "new@asdf.com", "password": "new-password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_pyschlage_auth.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "new@asdf.com", "password": "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_added_config_entry.data == {
        "username": "new@asdf.com",
        "password": "new-password",
    }


async def test_reconfigure_wrong_account(
    hass: HomeAssistant,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test the reconfigure flow rejects a different account."""
    result = await mock_added_config_entry.start_reconfigure_flow(hass)

    mock_pyschlage_auth.user_id = "bad-user-id"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "other@asdf.com", "password": "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_added_config_entry.data == {
        "username": "asdf@asdf.com",
        "password": "hunter2",
    }


async def test_reauth(
    hass: HomeAssistant,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test reauth flow."""
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    result = flows[-1]
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "new-password"},
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_added_config_entry.data == {
        "username": "asdf@asdf.com",
        "password": "new-password",
    }


async def test_reauth_invalid_auth(
    hass: HomeAssistant,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test the reauth flow handles invalid auth and recovers."""
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    mock_pyschlage_auth.authenticate.reset_mock()
    mock_pyschlage_auth.authenticate.side_effect = NotAuthorizedError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "new-password"},
    )

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    mock_pyschlage_auth.authenticate.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"password": "new-password"},
    )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert mock_added_config_entry.data == {
        "username": "asdf@asdf.com",
        "password": "new-password",
    }


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test reauth flow."""
    mock_pyschlage_auth.user_id = "bad-user-id"
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "new-password"},
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_account"
    assert mock_added_config_entry.data == {
        "username": "asdf@asdf.com",
        "password": "hunter2",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test a lock discovered over Bluetooth, including error recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=_bluetooth_discovery(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_pyschlage_auth.authenticate.side_effect = NotAuthorizedError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "test-username", "password": "test-password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_pyschlage_auth.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "test-username", "password": "test-password"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    assert result["result"].unique_id == "abc123"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_added_config_entry")
async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test Bluetooth discovery aborts when an account is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=_bluetooth_discovery(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_multiple_locks(hass: HomeAssistant) -> None:
    """Test a second discovered lock does not start another flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=_bluetooth_discovery(),
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=_bluetooth_discovery("AA:BB:CC:DD:EE:00"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_user_flow_replaces_bluetooth_discovery(
    hass: HomeAssistant, mock_pyschlage_auth: Mock
) -> None:
    """Test setting up the account manually dismisses the discovered flow."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=_bluetooth_discovery(),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "test-username", "password": "test-password"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "abc123"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
