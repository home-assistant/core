"""Test the Broadlink config flow."""
import errno
import socket

import broadlink.exceptions as blke
import pytest

from homeassistant import config_entries
from homeassistant.components.broadlink.const import DOMAIN

from . import pick_device

from tests.async_mock import MagicMock, call, patch


@pytest.fixture(autouse=True)
def broadlink_module_fixture():
    """Mock broadlink module."""
    broadlink = MagicMock()
    with patch.dict("sys.modules", {"broadlink": broadlink}):
        yield broadlink


@pytest.fixture(autouse=True)
def broadlink_setup_fixture():
    """Mock broadlink entry setup."""
    with patch(
        "homeassistant.components.broadlink.async_setup_entry", return_value=True
    ):
        yield


async def test_flow_user_works(hass):
    """Test a config flow initiated by the user.

    Best case scenario with no errors or locks.
    """
    device = pick_device(0)
    mock_device = device.get_mock_api()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch("broadlink.discover", return_value=[mock_device]) as mock_discover:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "finish"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": device.name},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()

    assert mock_discover.call_count == 1
    assert mock_device.auth.call_count == 1


async def test_flow_user_already_in_progress(hass):
    """Test we do not accept more than one config flow per device."""
    device = pick_device(0)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[device.get_mock_api()]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[device.get_mock_api()]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_flow_user_device_is_unique(hass):
    """Test we do not accept more than one config entry per device."""
    device = pick_device(0)
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    device.host = "192.168.1.240"  # The IP address has changed.
    mock_device = device.get_mock_api()

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host},
        )

    with patch(
        "homeassistant.components.broadlink.async_unload_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": device.name},
        )

    configured_macs = [
        entry.data.get("mac") for entry in hass.config_entries.async_entries(DOMAIN)
    ]

    assert len(configured_macs) == len(set(configured_macs))


async def test_flow_user_invalid_ip_address(hass):
    """Test we handle an invalid IP address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", side_effect=OSError(errno.EINVAL, None)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}


async def test_flow_user_invalid_hostname(hass):
    """Test we handle an invalid hostname."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", side_effect=OSError(socket.EAI_NONAME, None)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "pancakemaster.local"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}


async def test_flow_user_cannot_connect(hass):
    """Test we handle a device not found."""
    device = pick_device(0)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_auth_authentication_error(hass):
    """Test we handle an authentication error."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.auth.side_effect = blke.AuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reset"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_auth_cannot_connect(hass):
    """Test we handle a timeout error during authentication."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.auth.side_effect = blke.DeviceOfflineError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_auth_firmware_error(hass):
    """Test we handle a firmware error during authentication."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.auth.side_effect = blke.BroadlinkException()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_reset_works(hass):
    """Test we finish a config flow after a factory reset."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.auth.side_effect = blke.AuthenticationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    with patch("broadlink.discover", return_value=[device.get_mock_api()]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": device.name},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()


async def test_flow_unlock_works(hass):
    """Test a config flow with an unlock request."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.cloud = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "unlock"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"unlock": True},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": device.name},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()

    assert mock_device.set_lock.call_args == call(False)
    assert mock_device.set_lock.call_count == 1


async def test_flow_unlock_cannot_connect(hass):
    """Test we handle a timeout error during an unlock."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.cloud = True
    mock_device.set_lock.side_effect = blke.DeviceOfflineError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"unlock": True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "unlock"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_unlock_firmware_error(hass):
    """Test we handle a firmware error during an unlock."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.cloud = True
    mock_device.set_lock.side_effect = blke.BroadlinkException

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"unlock": True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "unlock"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_do_not_unlock(hass):
    """Test we do not unlock the device if the user does not want to."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.cloud = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"unlock": False},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": device.name},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()

    assert mock_device.set_lock.call_count == 0


async def test_flow_reauth_works(hass):
    """Test a reauthentication flow."""
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.auth.side_effect = blke.AuthenticationError()
    data = {"name": device.name, **device.get_entry_data()}

    with patch("broadlink.gendevice", return_value=mock_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth"}, data=data
        )

    with patch("broadlink.discover", return_value=[device.get_mock_api()]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": device.name},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()


async def test_flow_reauth_invalid_host(hass):
    """Test we do not accept an invalid host for reauthentication.

    The MAC address cannot change.
    """
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.auth.side_effect = blke.AuthenticationError()
    data = {"name": device.name, **device.get_entry_data()}

    with patch("broadlink.gendevice", return_value=mock_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth"}, data=data
        )

    wrong_device = pick_device(1)
    mock_wrong_device = wrong_device.get_mock_api()

    with patch("broadlink.discover", return_value=[mock_wrong_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": wrong_device.host, "timeout": device.timeout},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}


async def test_flow_reauth_valid_host(hass):
    """Test we accept a valid host for reauthentication.

    The hostname or IP address may change.
    """
    device = pick_device(0)
    mock_device = device.get_mock_api()
    mock_device.auth.side_effect = blke.AuthenticationError()
    data = {"name": device.name, **device.get_entry_data()}

    with patch("broadlink.gendevice", return_value=mock_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth"}, data=data
        )

    device.host = "192.168.1.240"  # The IP address has changed.
    mock_device = device.get_mock_api()

    with patch("broadlink.discover", return_value=[mock_device]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": device.host, "timeout": device.timeout},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": device.name},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == device.name
    assert result["data"] == device.get_entry_data()
