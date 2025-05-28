"""Test the Shelly config flow."""

from dataclasses import replace
from datetime import timedelta
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

from aioshelly.const import DEFAULT_HTTP_PORT, MODEL_1, MODEL_PLUS_2PM
from aioshelly.exceptions import (
    CustomPortNotSupported,
    DeviceConnectionError,
    InvalidAuthError,
    InvalidHostError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.shelly import MacAddressMismatchError, config_flow
from homeassistant.components.shelly.const import (
    CONF_BLE_SCANNER_MODE,
    CONF_GEN,
    CONF_SLEEP_PERIOD,
    DOMAIN,
    BLEScannerMode,
)
from homeassistant.components.shelly.coordinator import ENTRY_RELOAD_COOLDOWN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="mock_hostname",
    name="shelly1pm-12345",
    port=None,
    properties={ATTR_PROPERTIES_ID: "shelly1pm-12345"},
    type="mock_type",
)
DISCOVERY_INFO_WITH_MAC = ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="mock_hostname",
    name="shelly1pm-AABBCCDDEEFF",
    port=None,
    properties={ATTR_PROPERTIES_ID: "shelly1pm-AABBCCDDEEFF"},
    type="mock_type",
)


@pytest.mark.parametrize(
    ("gen", "model", "port"),
    [
        (1, MODEL_1, DEFAULT_HTTP_PORT),
        (2, MODEL_PLUS_2PM, DEFAULT_HTTP_PORT),
        (3, MODEL_PLUS_2PM, 11200),
    ],
)
async def test_form(
    hass: HomeAssistant,
    gen: int,
    model: str,
    port: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "test-mac",
                "type": MODEL_1,
                "auth": False,
                "gen": gen,
                "port": port,
            },
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: port},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: port,
        CONF_MODEL: model,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: gen,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_overrides_existing_discovery(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test setting up from the user flow when the devices is already discovered."""
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "AABBCCDDEEFF",
            "model": MODEL_PLUS_2PM,
            "auth": False,
            "gen": 2,
            "port": 80,
        },
    ):
        discovery_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZeroconfServiceInfo(
                ip_address=ip_address("1.1.1.1"),
                ip_addresses=[ip_address("1.1.1.1")],
                hostname="mock_hostname",
                name="shelly2pm-aabbccddeeff",
                port=None,
                properties={ATTR_PROPERTIES_ID: "shelly2pm-aabbccddeeff"},
                type="mock_type",
            ),
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert discovery_result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert result["context"]["unique_id"] == "AABBCCDDEEFF"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    # discovery flow should have been aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_form_gen1_custom_port(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={"mac": "test-mac", "type": MODEL_1, "gen": 1},
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create",
            side_effect=CustomPortNotSupported,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: "1100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "custom_port_not_supported"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "gen": 1},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_HTTP_PORT},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("gen", "model", "user_input", "username"),
    [
        (
            1,
            MODEL_1,
            {CONF_USERNAME: "test user", CONF_PASSWORD: "test1 password"},
            "test user",
        ),
        (
            2,
            MODEL_PLUS_2PM,
            {CONF_PASSWORD: "test2 password"},
            "admin",
        ),
        (
            3,
            MODEL_PLUS_2PM,
            {CONF_PASSWORD: "test2 password"},
            "admin",
        ),
    ],
)
async def test_form_auth(
    hass: HomeAssistant,
    gen: int,
    model: str,
    user_input: dict[str, str],
    username: str,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test manual configuration if auth is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": True, "gen": gen},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: model,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: gen,
        CONF_USERNAME: username,
        CONF_PASSWORD: user_input[CONF_PASSWORD],
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (InvalidHostError, "invalid_host"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors_get_info(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup: AsyncMock,
    mock_setup_entry: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.shelly.config_flow.get_info", side_effect=exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "gen": 1},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_model_key(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test we handle missing Shelly model key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    monkeypatch.setattr(mock_rpc_device, "shelly", {"gen": 2})
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False, "gen": "2"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


async def test_form_missing_model_key_auth_enabled(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test we handle missing Shelly model key when auth enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    monkeypatch.setattr(mock_rpc_device, "shelly", {"gen": 2})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "1234"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


async def test_form_missing_model_key_zeroconf(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test we handle missing Shelly model key via zeroconf."""
    monkeypatch.setattr(mock_rpc_device, "shelly", {"gen": 2})
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (MacAddressMismatchError, "mac_address_mismatch"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors_test_connection(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={"mac": "test-mac", "auth": False},
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create", new=AsyncMock(side_effect=exc)
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"


async def test_user_setup_ignored_device(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test user can successfully setup an ignored device."""

    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0"},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (InvalidAuthError, "invalid_auth"),
        (DeviceConnectionError, "cannot_connect"),
        (MacAddressMismatchError, "mac_address_mismatch"),
        (ValueError, "unknown"),
    ],
)
async def test_form_auth_errors_test_connection_gen1(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup: AsyncMock,
    mock_setup_entry: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors in Gen1 authenticated devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    with patch(
        "aioshelly.block_device.BlockDevice.create",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test username", CONF_PASSWORD: "test password"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test username", CONF_PASSWORD: "test password"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
        CONF_USERNAME: "test username",
        CONF_PASSWORD: "test password",
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (InvalidAuthError, "invalid_auth"),
        (MacAddressMismatchError, "mac_address_mismatch"),
        (ValueError, "unknown"),
    ],
)
async def test_form_auth_errors_test_connection_gen2(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    mock_setup: AsyncMock,
    mock_setup_entry: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors in Gen2 authenticated devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    with patch(
        "aioshelly.rpc_device.RpcDevice.create",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "test password"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test password"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: "SNSW-002P16EU",
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "test password",
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("gen", "model", "get_info"),
    [
        (
            1,
            MODEL_1,
            {"mac": "test-mac", "type": MODEL_1, "auth": False, "gen": 1},
        ),
        (
            2,
            MODEL_PLUS_2PM,
            {"mac": "test-mac", "model": MODEL_PLUS_2PM, "auth": False, "gen": 2},
        ),
        (
            3,
            MODEL_PLUS_2PM,
            {"mac": "test-mac", "model": MODEL_PLUS_2PM, "auth": False, "gen": 3},
        ),
    ],
)
async def test_zeroconf(
    hass: HomeAssistant,
    gen: int,
    model: str,
    get_info: dict[str, Any],
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info", return_value=get_info
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
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"
        assert context["confirm_only"] is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_MODEL: model,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: gen,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sleeping_device(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test sleeping device configuration via zeroconf."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 10, "unit": "m"},
    )
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "test-mac",
            "type": MODEL_1,
            "auth": False,
            "sleep_mode": True,
        },
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
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 600,
        CONF_GEN: 1,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sleeping_device_error(hass: HomeAssistant) -> None:
    """Test sleeping device configuration via zeroconf with error."""
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "test-mac",
                "type": MODEL_1,
                "auth": False,
                "sleep_mode": True,
            },
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create",
            new=AsyncMock(side_effect=DeviceConnectionError),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_options_flow_abort_setup_retry(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ble options abort if device is in setup retry."""
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=DeviceConnectionError)
    )
    entry = await init_integration(hass, 2)

    assert entry.state is ConfigEntryState.SETUP_RETRY

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_options_flow_abort_no_scripts_support(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ble options abort if device does not support scripts."""
    monkeypatch.setattr(
        mock_rpc_device, "supports_scripts", AsyncMock(return_value=False)
    )
    entry = await init_integration(hass, 2)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_scripts_support"


async def test_options_flow_abort_zigbee_enabled(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ble options abort if Zigbee is enabled for the device."""
    monkeypatch.setattr(mock_rpc_device, "zigbee_enabled", True)
    entry = await init_integration(hass, 4)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zigbee_enabled"


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"


async def test_zeroconf_ignored(hass: HomeAssistant) -> None:
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
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
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
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "2.2.2.2"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
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
    assert entry.data[CONF_HOST] == "2.2.2.2"


async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_require_auth(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test zeroconf if auth is required."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": True},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test username", CONF_PASSWORD: "test password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
        CONF_USERNAME: "test username",
        CONF_PASSWORD: "test password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("gen", "user_input"),
    [
        (1, {CONF_USERNAME: "test user", CONF_PASSWORD: "test1 password"}),
        (2, {CONF_PASSWORD: "test2 password"}),
        (3, {CONF_PASSWORD: "test2 password"}),
    ],
)
async def test_reauth_successful(
    hass: HomeAssistant,
    gen: int,
    user_input: dict[str, str],
    mock_block_device: Mock,
    mock_rpc_device: Mock,
) -> None:
    """Test starting a reauthentication flow."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": True, "gen": gen},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("gen", "user_input"),
    [
        (1, {CONF_USERNAME: "test user", CONF_PASSWORD: "test1 password"}),
        (2, {CONF_PASSWORD: "test2 password"}),
        (3, {CONF_PASSWORD: "test2 password"}),
    ],
)
@pytest.mark.parametrize(
    ("exc", "abort_reason"),
    [
        (DeviceConnectionError, "reauth_unsuccessful"),
        (MacAddressMismatchError, "mac_address_mismatch"),
    ],
)
async def test_reauth_unsuccessful(
    hass: HomeAssistant,
    gen: int,
    user_input: dict[str, str],
    exc: Exception,
    abort_reason: str,
) -> None:
    """Test reauthentication flow failed."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "test-mac",
                "type": MODEL_1,
                "auth": True,
                "gen": gen,
            },
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create", new=AsyncMock(side_effect=exc)
        ),
        patch("aioshelly.rpc_device.RpcDevice.create", new=AsyncMock(side_effect=exc)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


async def test_reauth_get_info_error(hass: HomeAssistant) -> None:
    """Test reauthentication flow failed with error in get_info()."""
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0", CONF_GEN: 2}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "test2 password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_unsuccessful"


async def test_options_flow_disabled_gen_1(
    hass: HomeAssistant, mock_block_device: Mock, hass_ws_client: WebSocketGenerator
) -> None:
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


async def test_options_flow_enabled_gen_2(
    hass: HomeAssistant, mock_rpc_device: Mock, hass_ws_client: WebSocketGenerator
) -> None:
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
    hass: HomeAssistant, mock_rpc_device: Mock, hass_ws_client: WebSocketGenerator
) -> None:
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


async def test_options_flow_ble(hass: HomeAssistant, mock_rpc_device: Mock) -> None:
    """Test setting ble options for gen2 devices."""
    entry = await init_integration(hass, 2)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.DISABLED,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] is BLEScannerMode.DISABLED

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] is BLEScannerMode.ACTIVE

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.PASSIVE,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] is BLEScannerMode.PASSIVE

    await hass.config_entries.async_unload(entry.entry_id)


async def test_zeroconf_already_configured_triggers_refresh_mac_in_name(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zeroconf discovery triggers refresh when the mac is in the device name."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 0,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO_WITH_MAC,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 2


async def test_zeroconf_already_configured_triggers_refresh(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zeroconf discovery triggers refresh when the mac is obtained via get_info."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 0,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 2


async def test_zeroconf_sleeping_device_not_triggers_refresh(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery does not triggers refresh for sleeping device."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1
    assert "device did not update" not in caplog.text


async def test_zeroconf_sleeping_device_attempts_configure(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery configures a sleeping device outbound websocket."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_rpc_device.update_outbound_websocket.mock_calls == []

    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert "device did not update" not in caplog.text

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    assert mock_rpc_device.update_outbound_websocket.mock_calls == [
        call("ws://10.10.10.10:8123/api/shelly/ws")
    ]


async def test_zeroconf_sleeping_device_attempts_configure_ws_disabled(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery configures a sleeping device outbound websocket when its disabled."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    monkeypatch.setitem(
        mock_rpc_device.config, "ws", {"enable": False, "server": "ws://oldha"}
    )
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_rpc_device.update_outbound_websocket.mock_calls == []

    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert "device did not update" not in caplog.text

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    assert mock_rpc_device.update_outbound_websocket.mock_calls == [
        call("ws://10.10.10.10:8123/api/shelly/ws")
    ]


async def test_zeroconf_sleeping_device_attempts_configure_no_url_available(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery for sleeping device with no hass url."""
    hass.config.internal_url = None
    hass.config.external_url = None
    hass.config.api = None
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_rpc_device.update_outbound_websocket.mock_calls == []

    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert "device did not update" not in caplog.text

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    # No url available so no attempt to configure the device
    assert mock_rpc_device.update_outbound_websocket.mock_calls == []


async def test_sleeping_device_gen2_with_new_firmware(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test sleeping device Gen2 with firmware 1.0.0 or later."""
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 666)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={"mac": "test-mac", "gen": 2},
        ),
        patch("homeassistant.components.shelly.async_setup", return_value=True),
        patch(
            "homeassistant.components.shelly.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 666,
        CONF_GEN: 2,
    }


@pytest.mark.parametrize(CONF_GEN, [1, 2, 3])
async def test_reconfigure_successful(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
) -> None:
    """Test starting a reconfiguration flow."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False, "gen": gen},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "10.10.10.10", CONF_PORT: 99, CONF_GEN: gen}


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_reconfigure_unsuccessful(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
) -> None:
    """Test reconfiguration flow failed."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "another-mac",
            "type": MODEL_1,
            "auth": False,
            "gen": gen,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "another_device"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (CustomPortNotSupported, "custom_port_not_supported"),
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
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0", CONF_GEN: 2}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch("homeassistant.components.shelly.config_flow.get_info", side_effect=exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "10.10.10.10", CONF_PORT: 99, CONF_GEN: 2}


async def test_zeroconf_rejects_ipv6(hass: HomeAssistant) -> None:
    """Test zeroconf discovery rejects ipv6."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("fd00::b27c:63bb:cc85:4ea0"),
            ip_addresses=[ip_address("fd00::b27c:63bb:cc85:4ea0")],
            hostname="mock_hostname",
            name="shelly1pm-12345",
            port=None,
            properties={ATTR_PROPERTIES_ID: "shelly1pm-12345"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ipv6_not_supported"
