"""Test the Shelly config flow."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

from aioshelly.exceptions import (
    DeviceConnectionError,
    FirmwareUnsupported,
    InvalidAuthError,
)
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.shelly import config_flow
from homeassistant.components.shelly.const import (
    CONF_BLE_SCANNER_MODE,
    DOMAIN,
    BLEScannerMode,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.setup import async_setup_component

from . import init_integration

from tests.common import MockConfigEntry

MOCK_SETTINGS = {
    "name": "Test name",
    "device": {"mac": "test-mac", "hostname": "test-host", "type": "SHSW-1"},
}
DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    host="1.1.1.1",
    addresses=["1.1.1.1"],
    hostname="mock_hostname",
    name="shelly1pm-12345",
    port=None,
    properties={zeroconf.ATTR_PROPERTIES_ID: "shelly1pm-12345"},
    type="mock_type",
)
DISCOVERY_INFO_WITH_MAC = zeroconf.ZeroconfServiceInfo(
    host="1.1.1.1",
    addresses=["1.1.1.1"],
    hostname="mock_hostname",
    name="shelly1pm-AABBCCDDEEFF",
    port=None,
    properties={zeroconf.ATTR_PROPERTIES_ID: "shelly1pm-AABBCCDDEEFF"},
    type="mock_type",
)
MOCK_CONFIG = {
    "sys": {
        "device": {"name": "Test name"},
    },
}


@pytest.mark.parametrize("gen", [1, 2])
async def test_form(hass, gen):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False, "gen": gen},
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(
            return_value=Mock(
                model="SHSW-1",
                settings=MOCK_SETTINGS,
            )
        ),
    ), patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(
            return_value=Mock(
                shelly={"model": "SHSW-1", "gen": gen},
                config=MOCK_CONFIG,
                shutdown=AsyncMock(),
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
        "gen": gen,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_title_without_name(hass):
    """Test we set the title to the hostname when the device doesn't have a name."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    settings = MOCK_SETTINGS.copy()
    settings["name"] = None
    settings["device"] = settings["device"].copy()
    settings["device"]["hostname"] = "shelly1pm-12345"
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(
            return_value=Mock(
                model="SHSW-1",
                settings=settings,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "shelly1pm-12345"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
        "gen": 1,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "test_data",
    [
        (1, {"username": "test user", "password": "test1 password"}, "test user"),
        (2, {"password": "test2 password"}, "admin"),
    ],
)
async def test_form_auth(hass, test_data):
    """Test manual configuration if auth is required."""
    gen, user_input, username = test_data
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True, "gen": gen},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(
            return_value=Mock(
                model="SHSW-1",
                settings=MOCK_SETTINGS,
            )
        ),
    ), patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(
            return_value=Mock(
                shelly={"model": "SHSW-1", "gen": gen},
                config=MOCK_CONFIG,
                shutdown=AsyncMock(),
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Test name"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
        "gen": gen,
        "username": username,
        "password": user_input["password"],
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "error", [(DeviceConnectionError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_form_errors_get_info(hass, error):
    """Test we handle errors."""
    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.shelly.config_flow.get_info", side_effect=exc):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": base_error}


async def test_form_missing_model_key(hass):
    """Test we handle missing Shelly model key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False, "gen": "2"},
    ), patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(
            return_value=Mock(
                shelly={"gen": 2},
                config=MOCK_CONFIG,
                shutdown=AsyncMock(),
            )
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "firmware_not_fully_provisioned"}


async def test_form_missing_model_key_auth_enabled(hass):
    """Test we handle missing Shelly model key when auth enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(
            return_value=Mock(
                shelly={"gen": 2},
                config=MOCK_CONFIG,
                shutdown=AsyncMock(),
            )
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"password": "1234"}
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": "firmware_not_fully_provisioned"}


async def test_form_missing_model_key_zeroconf(hass, caplog):
    """Test we handle missing Shelly model key via zeroconf."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False, "gen": 2},
    ), patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(
            return_value=Mock(
                shelly={"gen": 2},
                config=MOCK_CONFIG,
                shutdown=AsyncMock(),
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "firmware_not_fully_provisioned"}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["errors"] == {"base": "firmware_not_fully_provisioned"}


@pytest.mark.parametrize(
    "error", [(DeviceConnectionError, "cannot_connect"), (ValueError, "unknown")]
)
async def test_form_errors_test_connection(hass, error):
    """Test we handle errors."""
    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False},
    ), patch(
        "aioshelly.block_device.BlockDevice.create", new=AsyncMock(side_effect=exc)
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": base_error}


async def test_form_already_configured(hass):
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_user_setup_ignored_device(hass):
    """Test user can successfully setup an ignored device."""

    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={"host": "0.0.0.0"},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    settings = MOCK_SETTINGS.copy()
    settings["device"]["type"] = "SHSW-1"
    settings["fw"] = "20201124-092534/v1.9.0@57ac4ad8"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(
            return_value=Mock(
                model="SHSW-1",
                settings=settings,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_firmware_unsupported(hass):
    """Test we abort if device firmware is unsupported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=FirmwareUnsupported,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "unsupported_firmware"


@pytest.mark.parametrize(
    "error",
    [
        (InvalidAuthError, "invalid_auth"),
        (DeviceConnectionError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_auth_errors_test_connection_gen1(hass, error):
    """Test we handle errors in Gen1 authenticated devices."""
    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    with patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(side_effect=exc),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"username": "test username", "password": "test password"},
        )
    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": base_error}


@pytest.mark.parametrize(
    "error",
    [
        (DeviceConnectionError, "cannot_connect"),
        (InvalidAuthError, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_form_auth_errors_test_connection_gen2(hass, error):
    """Test we handle errors in Gen2 authenticated devices."""
    exc, base_error = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    with patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(side_effect=exc),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"password": "test password"}
        )
    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": base_error}


@pytest.mark.parametrize(
    "gen, get_info",
    [
        (1, {"mac": "test-mac", "type": "SHSW-1", "auth": False, "gen": 1}),
        (2, {"mac": "test-mac", "model": "SHSW-1", "auth": False, "gen": 2}),
    ],
)
async def test_zeroconf(hass, gen, get_info):
    """Test we get the form."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info", return_value=get_info
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(return_value=Mock(model="SHSW-1", settings=MOCK_SETTINGS)),
    ), patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(
            return_value=Mock(
                shelly={"model": "SHSW-1", "gen": gen},
                config=MOCK_CONFIG,
                shutdown=AsyncMock(),
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"
        assert context["confirm_only"] is True
    with patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
        "gen": gen,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sleeping_device(hass):
    """Test sleeping device configuration via zeroconf."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "test-mac",
            "type": "SHSW-1",
            "auth": False,
            "sleep_mode": True,
        },
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(
            return_value=Mock(
                model="SHSW-1",
                settings={
                    "name": "Test name",
                    "device": {
                        "mac": "test-mac",
                        "hostname": "test-host",
                        "type": "SHSW-1",
                    },
                    "sleep_mode": {"period": 10, "unit": "m"},
                },
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"
    with patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 600,
        "gen": 1,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sleeping_device_error(hass):
    """Test sleeping device configuration via zeroconf with error."""
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "test-mac",
            "type": "SHSW-1",
            "auth": False,
            "sleep_mode": True,
        },
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(side_effect=DeviceConnectionError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_already_configured(hass):
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_zeroconf_ignored(hass):
    """Test zeroconf when the device was previously ignored."""

    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_zeroconf_with_wifi_ap_ip(hass):
    """Test we ignore the Wi-FI AP IP."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "2.2.2.2"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=replace(DISCOVERY_INFO, host=config_flow.INTERNAL_WIFI_AP_IP),
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    # Test config entry was not updated with the wifi ap ip
    assert entry.data["host"] == "2.2.2.2"


async def test_zeroconf_firmware_unsupported(hass):
    """Test we abort if device firmware is unsupported."""
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=FirmwareUnsupported,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "unsupported_firmware"


async def test_zeroconf_cannot_connect(hass):
    """Test we get the form."""
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_require_auth(hass):
    """Test zeroconf if auth is required."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {}

    with patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(
            return_value=Mock(
                model="SHSW-1",
                settings=MOCK_SETTINGS,
            )
        ),
    ), patch(
        "homeassistant.components.shelly.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test username", "password": "test password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "SHSW-1",
        "sleep_period": 0,
        "gen": 1,
        "username": "test username",
        "password": "test password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "test_data",
    [
        (1, {"username": "test user", "password": "test1 password"}),
        (2, {"password": "test2 password"}),
    ],
)
async def test_reauth_successful(hass, test_data):
    """Test starting a reauthentication flow."""
    gen, user_input = test_data
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "0.0.0.0", "gen": gen}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True, "gen": gen},
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(
            return_value=Mock(
                model="SHSW-1",
                settings=MOCK_SETTINGS,
            )
        ),
    ), patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(
            return_value=Mock(
                shelly={"model": "SHSW-1", "gen": gen},
                config=MOCK_CONFIG,
                shutdown=AsyncMock(),
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    "test_data",
    [
        (1, {"username": "test user", "password": "test1 password"}),
        (2, {"password": "test2 password"}),
    ],
)
async def test_reauth_unsuccessful(hass, test_data):
    """Test reauthentication flow failed."""
    gen, user_input = test_data
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "0.0.0.0", "gen": gen}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": "SHSW-1", "auth": True, "gen": gen},
    ), patch(
        "aioshelly.block_device.BlockDevice.create",
        new=AsyncMock(side_effect=InvalidAuthError),
    ), patch(
        "aioshelly.rpc_device.RpcDevice.create",
        new=AsyncMock(side_effect=InvalidAuthError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_unsuccessful"


@pytest.mark.parametrize(
    "error",
    [DeviceConnectionError, FirmwareUnsupported],
)
async def test_reauth_get_info_error(hass, error):
    """Test reauthentication flow failed with error in get_info()."""
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={"host": "0.0.0.0", "gen": 2}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"password": "test2 password"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_unsuccessful"


async def test_options_flow_disabled_gen_1(hass, mock_block_device, hass_ws_client):
    """Test options are disabled for gen1 devices."""
    await async_setup_component(hass, "config", {})
    entry = await init_integration(hass, 1)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "shelly",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is False
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_enabled_gen_2(hass, mock_rpc_device, hass_ws_client):
    """Test options are enabled for gen2 devices."""
    await async_setup_component(hass, "config", {})
    entry = await init_integration(hass, 2)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "shelly",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is True
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_disabled_sleepy_gen_2(
    hass, mock_rpc_device, hass_ws_client
):
    """Test options are disabled for sleepy gen2 devices."""
    await async_setup_component(hass, "config", {})
    entry = await init_integration(hass, 2, sleep_period=10)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "shelly",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is False
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_ble(hass, mock_rpc_device):
    """Test setting ble options for gen2 devices."""
    entry = await init_integration(hass, 2)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.DISABLED,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] == BLEScannerMode.DISABLED

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] == BLEScannerMode.ACTIVE

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.PASSIVE,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] == BLEScannerMode.PASSIVE

    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_pre_ble_device(hass, mock_pre_ble_rpc_device):
    """Test setting ble options for gen2 devices with pre ble firmware."""
    entry = await init_integration(hass, 2)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.DISABLED,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] == BLEScannerMode.DISABLED

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "ble_unsupported"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.PASSIVE,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "ble_unsupported"

    await hass.config_entries.async_unload(entry.entry_id)


async def test_zeroconf_already_configured_triggers_refresh_mac_in_name(
    hass, mock_rpc_device, monkeypatch
):
    """Test zeroconf discovery triggers refresh when the mac is in the device name."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={"host": "1.1.1.1", "gen": 2, "sleep_period": 0, "model": "SHSW-1"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO_WITH_MAC,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 2


async def test_zeroconf_already_configured_triggers_refresh(
    hass, mock_rpc_device, monkeypatch
):
    """Test zeroconf discovery triggers refresh when the mac is obtained via get_info."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={"host": "1.1.1.1", "gen": 2, "sleep_period": 0, "model": "SHSW-1"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 2


async def test_zeroconf_sleeping_device_not_triggers_refresh(
    hass, mock_rpc_device, monkeypatch, caplog
):
    """Test zeroconf discovery does not triggers refresh for sleeping device."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={"host": "1.1.1.1", "gen": 2, "sleep_period": 1000, "model": "SHSW-1"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_rpc_device.mock_update()

    assert "online, resuming setup" in caplog.text

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": "SHSW-1", "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 0
    assert "device did not update" not in caplog.text
