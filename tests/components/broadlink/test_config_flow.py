"""Test the Broadlink config flow."""

import errno
import socket
from unittest.mock import call, patch

import broadlink.exceptions as blke
import pytest

from homeassistant import config_entries
from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import get_device

DEVICE_HELLO = "homeassistant.components.broadlink.config_flow.blk.hello"
DEVICE_FACTORY = "homeassistant.components.broadlink.config_flow.blk.gendevice"


@pytest.fixture(autouse=True)
def broadlink_setup_fixture():
    """Mock broadlink entry setup."""
    with (
        patch("homeassistant.components.broadlink.async_setup", return_value=True),
        patch(
            "homeassistant.components.broadlink.async_setup_entry", return_value=True
        ),
    ):
        yield


@pytest.mark.parametrize("device_name", ["Living Room", "Study"])
async def test_flow_user_works(hass: HomeAssistant, device_name: str) -> None:
    """Test a config flow initiated by the user.

    Best case scenario with no errors or locks.
    """
    device = get_device(device_name)
    mock_api = device.get_mock_api()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(DEVICE_HELLO, return_value=mock_api) as mock_hello:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()

    assert mock_hello.call_count == 1
    assert mock_api.auth.call_count == 1


async def test_flow_user_falls_back_to_model_as_title(hass: HomeAssistant) -> None:
    """Test the model is used as the title when the device reports no name."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.name = ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device.model


async def test_flow_user_already_in_progress(hass: HomeAssistant) -> None:
    """Test we do not accept more than one config flow per device."""
    device = get_device("Living Room")
    locked_api = device.get_mock_api()
    locked_api.is_locked = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # A locked device waits for the user, so the first flow stays in progress.
    with patch(DEVICE_HELLO, return_value=locked_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=device.get_mock_api()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_flow_user_mac_already_configured(hass: HomeAssistant) -> None:
    """Test we do not accept more than one config entry per device.

    We need to abort the flow and update the existing entry.
    """
    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    device.host = "192.168.1.64"
    device.timeout = 20
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert dict(mock_entry.data) == device.get_entry_data()
    assert mock_api.auth.call_count == 0


async def test_flow_user_invalid_ip_address(hass: HomeAssistant) -> None:
    """Test we handle an invalid IP address in the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, side_effect=OSError(errno.EINVAL, None)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "0.0.0.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}


async def test_flow_user_invalid_hostname(hass: HomeAssistant) -> None:
    """Test we handle an invalid hostname in the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, side_effect=OSError(socket.EAI_NONAME, None)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "pancakemaster.local"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}


async def test_flow_user_device_not_found(hass: HomeAssistant) -> None:
    """Test we handle a device not found in the user step."""
    device = get_device("Living Room")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, side_effect=blke.NetworkTimeoutError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_device_not_supported(hass: HomeAssistant) -> None:
    """Test we handle a device not supported in the user step."""
    device = get_device("Kitchen")
    mock_api = device.get_mock_api()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_flow_user_network_unreachable(hass: HomeAssistant) -> None:
    """Test we handle a network unreachable in the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, side_effect=OSError(errno.ENETUNREACH, None)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.32"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_os_error(hass: HomeAssistant) -> None:
    """Test we handle an OS error in the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, side_effect=OSError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.32"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_auth_authentication_error(hass: HomeAssistant) -> None:
    """Test we handle an authentication error in the auth step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reset"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_auth_network_timeout(hass: HomeAssistant) -> None:
    """Test we handle a network timeout in the auth step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.NetworkTimeoutError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_auth_firmware_error(hass: HomeAssistant) -> None:
    """Test we handle a firmware error in the auth step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.BroadlinkException()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_auth_network_unreachable(hass: HomeAssistant) -> None:
    """Test we handle a network unreachable in the auth step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = OSError(errno.ENETUNREACH, None)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_auth_os_error(hass: HomeAssistant) -> None:
    """Test we handle an OS error in the auth step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = OSError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_reset_works(hass: HomeAssistant) -> None:
    """Test we finish a config flow after a manual unlock."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    unlocked_api = device.get_mock_api()
    with patch(DEVICE_HELLO, return_value=unlocked_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    # The first probe opened its endpoint in auth(); replacing it closes it.
    assert mock_api.aclose.await_count == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()
    await hass.async_block_till_done()
    assert unlocked_api.aclose.await_count == 1


async def test_flow_unlock_works(hass: HomeAssistant) -> None:
    """Test we finish a config flow with an unlock request."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.is_locked = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"unlock": True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()

    assert mock_api.set_lock.call_args == call(False)
    assert mock_api.set_lock.call_count == 1


async def test_flow_unlock_network_timeout(hass: HomeAssistant) -> None:
    """Test we handle a network timeout in the unlock step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.is_locked = True
    mock_api.set_lock.side_effect = blke.NetworkTimeoutError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"unlock": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_unlock_firmware_error(hass: HomeAssistant) -> None:
    """Test we handle a firmware error in the unlock step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.is_locked = True
    mock_api.set_lock.side_effect = blke.BroadlinkException

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"unlock": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_unlock_network_unreachable(hass: HomeAssistant) -> None:
    """Test we handle a network unreachable in the unlock step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.is_locked = True
    mock_api.set_lock.side_effect = OSError(errno.ENETUNREACH, None)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"unlock": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_unlock_os_error(hass: HomeAssistant) -> None:
    """Test we handle an OS error in the unlock step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.is_locked = True
    mock_api.set_lock.side_effect = OSError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"unlock": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_do_not_unlock(hass: HomeAssistant) -> None:
    """Test we do not unlock the device if the user does not want to."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.is_locked = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"unlock": False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()

    assert mock_api.set_lock.call_count == 0


async def test_flow_import_works(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an import flow."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api) as mock_hello:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": device.host},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device.name
    assert result["data"]["host"] == device.host
    assert result["data"]["mac"] == device.mac
    assert result["data"]["type"] == device.devtype

    assert mock_api.auth.call_count == 1
    assert mock_hello.call_count == 1

    # The entry is created right away, so there is nothing left to configure.
    assert "is ready to be configured" not in caplog.text


async def test_flow_import_locked_device_logs_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an imported locked device tells the user to finish the setup."""
    device = get_device("Living Room")
    locked_api = device.get_mock_api()
    locked_api.is_locked = True

    with patch(DEVICE_HELLO, return_value=locked_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": device.host},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"
    assert "is ready to be configured" in caplog.text


async def test_flow_import_already_in_progress(hass: HomeAssistant) -> None:
    """Test we do not import more than one flow per device."""
    device = get_device("Living Room")
    data = {"host": device.host}
    locked_api = device.get_mock_api()
    locked_api.is_locked = True

    # A locked device waits for the user, so the first flow stays in progress.
    with patch(DEVICE_HELLO, return_value=locked_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )

    with patch(DEVICE_HELLO, return_value=device.get_mock_api()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_flow_import_host_already_configured(hass: HomeAssistant) -> None:
    """Test we do not import a host that is already configured."""
    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": device.host},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import_mac_already_configured(hass: HomeAssistant) -> None:
    """Test we do not import more than one config entry per device.

    We need to abort the flow and update the existing entry.
    """
    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device.host = "192.168.1.16"
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": device.host},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_entry.data["host"] == device.host
    assert mock_entry.data["mac"] == device.mac
    assert mock_entry.data["type"] == device.devtype
    assert mock_api.auth.call_count == 0


async def test_flow_import_device_not_found(hass: HomeAssistant) -> None:
    """Test we handle a device not found in the import step."""
    with patch(DEVICE_HELLO, side_effect=blke.NetworkTimeoutError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "192.168.1.32"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_import_device_not_supported(hass: HomeAssistant) -> None:
    """Test we handle a device not supported in the import step."""
    device = get_device("Kitchen")
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": device.host},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_flow_import_invalid_ip_address(hass: HomeAssistant) -> None:
    """Test we handle an invalid IP address in the import step."""
    with patch(DEVICE_HELLO, side_effect=OSError(errno.EINVAL, None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "0.0.0.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_host"


async def test_flow_import_invalid_hostname(hass: HomeAssistant) -> None:
    """Test we handle an invalid hostname in the import step."""
    with patch(DEVICE_HELLO, side_effect=OSError(socket.EAI_NONAME, None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "hotdog.local"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_host"


async def test_flow_import_network_unreachable(hass: HomeAssistant) -> None:
    """Test we handle a network unreachable in the import step."""
    with patch(DEVICE_HELLO, side_effect=OSError(errno.ENETUNREACH, None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "192.168.1.64"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_import_os_error(hass: HomeAssistant) -> None:
    """Test we handle an OS error in the import step."""
    with patch(DEVICE_HELLO, side_effect=OSError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "192.168.1.64"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_flow_reauth_works(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()

    with patch(DEVICE_FACTORY, return_value=mock_api):
        result = await mock_entry.start_reauth_flow(hass, data={"name": device.name})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reset"

    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api) as mock_hello:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert dict(mock_entry.data) == device.get_entry_data()
    assert mock_api.auth.call_count == 1
    assert mock_hello.call_count == 1


async def test_flow_reauth_invalid_host(hass: HomeAssistant) -> None:
    """Test we do not accept an invalid host for reauthentication.

    The MAC address cannot change.
    """
    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()
    with patch(DEVICE_FACTORY, return_value=mock_api):
        result = await mock_entry.start_reauth_flow(hass, data={"name": device.name})

    device.mac = get_device("Office").mac
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api) as mock_hello:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}

    assert mock_hello.call_count == 1
    assert mock_api.auth.call_count == 0


async def test_flow_reauth_valid_host(hass: HomeAssistant) -> None:
    """Test we accept a valid host for reauthentication.

    The hostname/IP address may change. We need to update the entry.
    """
    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()

    with patch(DEVICE_FACTORY, return_value=mock_api):
        result = await mock_entry.start_reauth_flow(hass, data={"name": device.name})

    device.host = "192.168.1.128"
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api) as mock_hello:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_entry.data["host"] == device.host
    assert mock_hello.call_count == 1
    assert mock_api.auth.call_count == 1


async def test_dhcp_can_finish(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow can finish right away."""

    device = get_device("Living Room")
    device.host = "1.2.3.4"
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip="1.2.3.4",
                macaddress=device.mac,
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {
        "host": "1.2.3.4",
        "mac": "34ea34b43b5a",
        "timeout": 10,
        "type": 24374,
    }


async def test_dhcp_locked_device_without_name_shows_model(
    hass: HomeAssistant,
) -> None:
    """Test the model replaces an empty device name in the flow placeholders."""
    device = get_device("Living Room")
    device.host = "1.2.3.4"
    locked_api = device.get_mock_api()
    locked_api.name = ""
    locked_api.is_locked = True

    with patch(DEVICE_HELLO, return_value=locked_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip="1.2.3.4",
                macaddress=device.mac,
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unlock"
    assert result["description_placeholders"]["name"] == device.model
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["title_placeholders"]["name"] == device.model


async def test_dhcp_fails_to_connect(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow that fails to connect."""

    with patch(DEVICE_HELLO, side_effect=blke.NetworkTimeoutError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip="1.2.3.4",
                macaddress="34ea34b43b5a",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_dhcp_unreachable(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow that fails to connect."""

    with patch(DEVICE_HELLO, side_effect=OSError(errno.ENETUNREACH, None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip="1.2.3.4",
                macaddress="34ea34b43b5a",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_dhcp_connect_unknown_error(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow that fails to connect with an OSError."""

    with patch(DEVICE_HELLO, side_effect=OSError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip="1.2.3.4",
                macaddress="34ea34b43b5a",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_dhcp_device_not_supported(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow that fails because the device is not supported."""

    device = get_device("Kitchen")
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip=device.host,
                macaddress=device.mac,
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_dhcp_already_exists(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow that fails to connect."""

    device = get_device("Living Room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)
    device.host = "1.2.3.4"
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip="1.2.3.4",
                macaddress="34ea34b43b5a",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_updates_host(hass: HomeAssistant) -> None:
    """Test DHCP updates host."""

    device = get_device("Living Room")
    device.host = "1.2.3.4"
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)
    mock_api = device.get_mock_api()

    with patch(DEVICE_HELLO, return_value=mock_api):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="broadlink",
                ip="4.5.6.7",
                macaddress="34ea34b43b5a",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_entry.data["host"] == "4.5.6.7"
