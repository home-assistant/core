"""Test the refoss_rpc config flow."""

from dataclasses import replace
from ipaddress import ip_address
from unittest.mock import AsyncMock, Mock, patch

from aiorefoss.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.refoss_rpc import config_flow
from homeassistant.components.refoss_rpc.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info import zeroconf

from tests.common import MockConfigEntry

DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="refoss-r11-743af4da2f5a",
    name="refoss-r11-743af4da2f5a._http._tcp.local.",
    port=None,
    properties={zeroconf.ATTR_PROPERTIES_ID: "refoss-r11-743af4da2f5a"},
    type="mock_type",
)


async def test_form(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.refoss_rpc.config_flow.get_info",
            return_value={
                "name": "Test name",
                "mac": "test-mac",
                "model": "r11",
                "dev_id": "refoss-r11-743af4da2f5a",
                "fw_ver": "1.0.0",
                "hw_ver": "1.0.1",
                "auth_en": False,
            },
        ),
        patch(
            "homeassistant.components.refoss_rpc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "mac": "test-mac",
        "host": "1.1.1.1",
        "model": "r11",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("model", "user_input"),
    [
        (
            "r11",
            {"password": "test password"},
        ),
    ],
)
async def test_form_auth(
    hass: HomeAssistant,
    model: str,
    user_input: dict[str, str],
    mock_rpc_device: Mock,
) -> None:
    """Test manual configuration if auth is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "mac": "test-mac",
            "model": "r11",
            "dev_id": "refoss-r11-743af4da2f5a",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": True,
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.refoss_rpc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Test name"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "model": model,
        "mac": "test-mac",
        "username": "admin",
        "password": user_input["password"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
    ],
)
async def test_form_errors_get_info(
    hass: HomeAssistant, exc: Exception, base_error: str
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info", side_effect=exc
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": base_error}


async def test_form_missing_model_key(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test we handle missing refoss model."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    monkeypatch.setattr(mock_rpc_device, "model", None)
    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "firmware_not_fully_supported"}


async def test_form_missing_model_key_auth_enabled(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test we handle missing refoss model key when auth enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": True,
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    monkeypatch.setattr(mock_rpc_device, "model", None)
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"password": "1234"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "firmware_not_fully_supported"}


async def test_form_missing_model_key_zeroconf(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test we handle missing refoss model key via zeroconf."""
    monkeypatch.setattr(mock_rpc_device, "model", None)
    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "firmware_not_fully_supported"}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "firmware_not_fully_supported"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_user_setup_ignored_device(
    hass: HomeAssistant, mock_rpc_device: Mock
) -> None:
    """Test user can successfully setup an ignored device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-mac",
        data={"host": "0.0.0.0"},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.refoss_rpc.config_flow.get_info",
            return_value={
                "name": "Test name",
                "model": "r11",
                "mac": "test-mac",
                "fw_ver": "1.0.0",
                "hw_ver": "1.0.1",
                "auth_en": False,
            },
        ),
        patch(
            "homeassistant.components.refoss_rpc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (InvalidAuthError, "invalid_auth"),
        (MacAddressMismatchError, "mac_address_mismatch"),
    ],
)
async def test_form_auth_errors_test_connection_gen2(
    hass: HomeAssistant, exc: Exception, base_error: str
) -> None:
    """Test we handle errors in  authenticated devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": True,
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    with patch(
        "aiorefoss.rpc_device.RpcDevice.create",
        new=AsyncMock(side_effect=exc),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"password": "test password"}
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": base_error}


async def test_zeroconf(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test we get the form."""
    with (
        patch(
            "homeassistant.components.refoss_rpc.config_flow.get_info",
            return_value={
                "name": "Test name",
                "model": "r11",
                "mac": "test-mac",
                "fw_ver": "1.0.0",
                "hw_ver": "1.0.1",
                "auth_en": False,
            },
        ),
        patch(
            "homeassistant.components.refoss_rpc.config_flow.mac_address_from_name",
            return_value="test-mac",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "Test name"
        assert context["confirm_only"] is True
    with (
        patch(
            "homeassistant.components.refoss_rpc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "mac": "test-mac",
        "host": "1.1.1.1",
        "model": "r11",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_zeroconf_ignored(hass: HomeAssistant) -> None:
    """Test zeroconf when the device was previously ignored."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-mac",
        data={},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_zeroconf_with_wifi_ap_ip(hass: HomeAssistant) -> None:
    """Test we ignore the Wi-FI AP IP."""

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "10.10.10.1"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=replace(
                DISCOVERY_INFO, ip_address=ip_address(config_flow.INTERNAL_WIFI_AP_IP)
            ),
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    # Test config entry was not updated with the wifi ap ip
    assert entry.data["host"] == "10.10.10.1"


async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_cannot_connect_initialize(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        monkeypatch.setattr(
            mock_rpc_device,
            "initialize",
            AsyncMock(side_effect=DeviceConnectionError),
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_require_auth(
    hass: HomeAssistant, mock_rpc_device: Mock
) -> None:
    """Test zeroconf if auth is required."""

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": True,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.refoss_rpc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "mac": "test-mac",
        "model": "r11",
        "username": "admin",
        "password": "test",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test starting a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": True,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"password": "test password"},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("exc", "abort_reason"),
    [
        (DeviceConnectionError, "reauth_unsuccessful"),
        (MacAddressMismatchError, "mac_address_mismatch"),
    ],
)
async def test_reauth_unsuccessful(
    hass: HomeAssistant,
    exc: Exception,
    abort_reason: str,
) -> None:
    """Test reauthentication flow failed."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.refoss_rpc.config_flow.get_info",
            return_value={
                "name": "Test name",
                "model": "r11",
                "mac": "test-mac",
                "fw_ver": "1.0.0",
                "hw_ver": "1.0.1",
                "auth_en": True,
            },
        ),
        patch("aiorefoss.rpc_device.RpcDevice.create", new=AsyncMock(side_effect=exc)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"password": "test password"},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == abort_reason


async def test_reauth_get_info_error(hass: HomeAssistant) -> None:
    """Test reauthentication flow failed with error in get_info()."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"password": "test password"},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_unsuccessful"


async def test_reconfigure_successful(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test starting a reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "test-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "10.10.10.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {"host": "10.10.10.1"}


async def test_reconfigure_unsuccessful(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test reconfiguration flow failed."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "model": "r11",
            "mac": "another-mac",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "10.10.10.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "another_device"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
    ],
)
async def test_reconfigure_with_exception(
    hass: HomeAssistant,
    exc: Exception,
    base_error: str,
    mock_rpc_device: Mock,
) -> None:
    """Test reconfiguration flow when an exception is raised."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info", side_effect=exc
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "10.10.10.1"},
        )

    assert result["errors"] == {"base": base_error}


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (MacAddressMismatchError, "mac_address_mismatch"),
    ],
)
async def test_form_errors_test_connection(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    exc: Exception,
    base_error: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.refoss_rpc.config_flow.get_info",
        return_value={
            "name": "Test name",
            "mac": "test-mac",
            "model": "r11",
            "dev_id": "refoss-r11-743af4da2f5a",
            "fw_ver": "1.0.0",
            "hw_ver": "1.0.1",
            "auth_en": False,
        },
    ):
        monkeypatch.setattr(mock_rpc_device, "initialize", AsyncMock(side_effect=exc))
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": base_error}
