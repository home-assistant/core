"""Test the airlino config flow."""

from collections.abc import AsyncGenerator
from ipaddress import IPv4Address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.airlino.api import (
    AirlinoApiConnectionError,
    AirlinoApiError,
)
from homeassistant.components.airlino.config_flow import (
    CannotConnect,
    CannotIdentify,
    UnsupportedApiVersion,
    _get_mac,
    _txt_str,
    validate_input,
)
from homeassistant.components.airlino.const import (
    DEFAULT_API_VERSION,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

MAC = "00:11:22:33:44:55"
HOST = "192.168.178.42"


def _discovery_info(
    *,
    properties: dict[str, Any] | None = None,
    port: int = DEFAULT_PORT,
    hostname: str = "AirLinopro-12AB.local.",
    name: str = "Livingroom._dockset._tcp.local.",
) -> ZeroconfServiceInfo:
    """Build service information for a discovered AirLino."""
    address = IPv4Address(HOST)
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        port=port,
        hostname=hostname,
        type="_dockset._tcp.local.",
        name=name,
        properties={"model": "AirLino"} if properties is None else properties,
    )


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (UnsupportedApiVersion, "unsupported_api_version"),
        (CannotConnect, "cannot_connect"),
        (CannotIdentify, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_recovers_from_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    expected_error: str,
) -> None:
    """Verify user setup recovers after validation errors."""
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        side_effect=[
            exception("failure"),
            {"title": "Living Room", "mac": MAC, "api_version": "v22"},
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["data_schema"] is not None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {
        CONF_HOST: HOST,
        "port": DEFAULT_PORT,
        "api_version": "v22",
    }


async def test_user_flow_uses_custom_port(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Verify user setup retains a configured port."""
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        return_value={
            "title": "AirLino",
            "mac": MAC,
            "api_version": "v21",
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, "port": 9000}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["port"] == 9000
    assert result["data"]["api_version"] == "v21"


async def test_user_flow_aborts_if_device_is_configured(hass: HomeAssistant) -> None:
    """Verify user setup rejects a previously configured device."""
    MockConfigEntry(domain=DOMAIN, unique_id=MAC).add_to_hass(hass)
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        return_value={"title": "AirLino", "mac": MAC, "api_version": "v22"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_aborts_duplicate_in_progress_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an in-progress duplicate setup is aborted."""
    aborted_flow_id = "another-flow"
    monkeypatch.setattr(
        hass.config_entries.flow,
        "async_progress_by_handler",
        MagicMock(
            return_value=[{"flow_id": aborted_flow_id, "context": {"unique_id": MAC}}]
        ),
    )
    abort = MagicMock()
    monkeypatch.setattr(hass.config_entries.flow, "async_abort", abort)
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        return_value={"title": "AirLino", "mac": MAC, "api_version": "v22"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )

    abort.assert_any_call(aborted_flow_id)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.fixture
async def mock_setup_entry() -> AsyncGenerator[AsyncMock]:
    """Mock entry setup to prevent post-flow network requests."""
    with patch(
        "homeassistant.components.airlino.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.mark.parametrize(
    ("discovery", "reason"),
    [
        (_discovery_info(properties={"model": "Other"}), "not_airlino"),
    ],
)
async def test_zeroconf_flow_aborts_invalid_discovery(
    hass: HomeAssistant, discovery: ZeroconfServiceInfo, reason: str
) -> None:
    """Verify unsupported models are rejected during discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (UnsupportedApiVersion, "unsupported_api_version"),
        (CannotConnect, "cannot_connect"),
        (CannotIdentify, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_zeroconf_flow_aborts_on_validation_errors(
    hass: HomeAssistant, exception: type[Exception], reason: str
) -> None:
    """Verify zeroconf setup aborts when validation fails."""
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        side_effect=exception("failure"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_zeroconf_flow_confirms_and_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Verify discovered devices can be confirmed and added."""
    validate = AsyncMock(
        return_value={"title": "Living Room", "mac": MAC, "api_version": "v22"}
    )
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        validate,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=_discovery_info(
                properties={
                    "api": "v22",
                    "swver": "6.4.1",
                    "model": "AirLino pro",
                },
                port=DEFAULT_PORT,
                hostname="AirLinopro-12AB.local.",
                name="Livingroom._dockset._tcp.local.",
            ),
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert result["description_placeholders"] == {"name": "Living Room"}

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"]["port"] == DEFAULT_PORT
    assert result["data"]["api_version"] == "v22"


async def test_zeroconf_flow_uses_default_values(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Verify zeroconf defaults are used when records omit values."""
    discovery = _discovery_info(properties={"model": "AirLino"}, port=0)
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        return_value={
            "title": "AirLino",
            "mac": MAC,
            "api_version": DEFAULT_API_VERSION,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["data"]["port"] == DEFAULT_PORT
    assert result["data"]["api_version"] == DEFAULT_API_VERSION


async def test_zeroconf_flow_aborts_if_device_is_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Verify discovery rejects an already configured device."""
    MockConfigEntry(domain=DOMAIN, unique_id=MAC).add_to_hass(hass)
    with patch(
        "homeassistant.components.airlino.config_flow.validate_input",
        return_value={"title": "AirLino", "mac": MAC, "api_version": "v22"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("network_info", "expected"),
    [
        (
            {
                "eth": {"mac": "00:23:b1:a4:35:9e"},
                "wlan": {"mac": "00:23:b1:66:ab:94"},
            },
            "00:23:b1:a4:35:9e",
        ),
        (
            {
                "wlan": {
                    "mac": "00:23:b1:66:ab:94",
                    "mode": "station",
                    "ssid": "AirLino-WLAN",
                    "inet": [{"family": "inet", "ip": "192.0.2.20"}],
                }
            },
            "00:23:b1:66:ab:94",
        ),
        ({"eth": {}, "wlan": {}}, None),
        ({}, None),
    ],
)
def test_get_mac(network_info: dict[str, Any], expected: str | None) -> None:
    """Verify Ethernet MAC is preferred over WLAN MAC."""
    assert _get_mac(network_info) == expected


@pytest.mark.parametrize(
    ("properties", "key", "expected"),
    [
        ({}, "missing", None),
        ({"key": b"value"}, "key", "value"),
        ({"key": bytearray(b"value")}, "key", "value"),
        ({"key": [b"value", b"ignored"]}, "key", "value"),
        ({"key": [bytearray(b"value")]}, "key", "value"),
        ({"key": b"\xff"}, "key", "�"),
        ({"key": []}, "key", None),
        ({"key": ["value"]}, "key", "value"),
        ({"key": [None]}, "key", None),
        ({"key": 123}, "key", "123"),
    ],
)
def test_txt_str(properties: dict[str, Any], key: str, expected: str | None) -> None:
    """Verify zeroconf TXT values are normalized to strings."""
    assert _txt_str(properties, key) == expected


async def test_validate_input_uses_latest_version_and_ethernet_mac(
    hass: HomeAssistant,
) -> None:
    """Verify validation uses the newest API and prefers Ethernet MAC."""
    api = MagicMock()
    api.async_get_device_info = AsyncMock(
        return_value={
            "model": "HBM11",
            "devicename": "Living Room",
            "firmware": "6.3.3",
            "hardware": "LTH-6510CC-02DAA9A6",
        }
    )
    api.async_get_network_info = AsyncMock(
        return_value={
            "eth": {
                "mac": "00:23:b1:a4:35:9e",
                "inet": [{"family": "inet", "ip": "192.0.2.20"}],
            },
            "wlan": {
                "mac": "00:23:b1:66:ab:94",
                "mode": "station",
                "ssid": "AirLino-WLAN",
                "inet": [{"family": "inet", "ip": "192.0.2.21"}],
            },
        }
    )
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.airlino.config_flow.AirlinoApi",
            return_value=api,
        ) as api_class,
    ):
        result = await validate_input(hass, {CONF_HOST: HOST, "port": 8989})

    assert result == {
        "title": "Living Room",
        "mac": "00:23:b1:a4:35:9e",
        "api_version": DEFAULT_API_VERSION,
    }
    assert api_class.call_args.kwargs["host"] == HOST
    assert api_class.call_args.kwargs["port"] == DEFAULT_PORT
    assert api_class.call_args.kwargs["api_version"] == DEFAULT_API_VERSION


async def test_validate_input_falls_back_to_older_api_version(
    hass: HomeAssistant,
) -> None:
    """Verify validation tries supported API versions until one works."""
    apis = [MagicMock() for _ in range(4)]
    apis[0].async_get_device_info = AsyncMock(
        side_effect=AirlinoApiError("missing", status=404)
    )
    apis[1].async_get_device_info = AsyncMock(side_effect=AirlinoApiError("failed"))
    apis[2].async_get_device_info = AsyncMock(
        return_value={
            "model": "HBM11",
            "devicename": "Living Room",
            "firmware": "6.3.3",
            "hardware": "LTH-6510CC-02DAA9A6",
        }
    )
    apis[2].async_get_network_info = AsyncMock(
        return_value={"wlan": {"mac": "00:23:b1:66:ab:94"}}
    )
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.airlino.config_flow.AirlinoApi",
            side_effect=apis,
        ) as api_class,
    ):
        result = await validate_input(hass, {CONF_HOST: HOST})

    assert result["api_version"] == "v20"
    assert result["title"] == "Living Room"
    assert result["mac"] == "00:23:b1:66:ab:94"
    assert [call.kwargs["api_version"] for call in api_class.call_args_list] == [
        "v22",
        "v21",
        "v20",
    ]


async def test_validate_input_raises_unsupported_when_no_version_works(
    hass: HomeAssistant,
) -> None:
    """Verify validation rejects devices without a supported API."""
    api = MagicMock()
    api.async_get_device_info = AsyncMock(
        side_effect=AirlinoApiError("missing", status=404)
    )
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.airlino.config_flow.AirlinoApi",
            return_value=api,
        ),
        pytest.raises(UnsupportedApiVersion),
    ):
        await validate_input(hass, {CONF_HOST: HOST})


@pytest.mark.parametrize(
    "error",
    [
        AirlinoApiError("failed", status=500),
        AirlinoApiConnectionError("offline"),
        aiohttp.ClientError("offline"),
    ],
)
async def test_validate_input_maps_connection_errors(
    hass: HomeAssistant, error: Exception
) -> None:
    """Verify API connection failures become CannotConnect errors."""
    api = MagicMock()
    api.async_get_device_info = AsyncMock(side_effect=error)
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.airlino.config_flow.AirlinoApi",
            return_value=api,
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(hass, {CONF_HOST: HOST}, api_version="v22")


async def test_validate_input_uses_default_port_and_announced_version(
    hass: HomeAssistant,
) -> None:
    """Verify validation uses port 8989 and the announced API version."""
    api = MagicMock()
    api.async_get_device_info = AsyncMock(
        return_value={
            "model": "HBM11",
            "devicename": "Living Room",
            "firmware": "6.3.3",
            "hardware": "LTH-6510CC-02DAA9A6",
        }
    )
    api.async_get_network_info = AsyncMock(
        return_value={"eth": {"mac": "00:23:b1:a4:35:9e"}}
    )
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.airlino.config_flow.AirlinoApi",
            return_value=api,
        ) as api_class,
    ):
        result = await validate_input(
            hass, {CONF_HOST: HOST, "port": DEFAULT_PORT}, api_version="v22"
        )

    assert result["api_version"] == "v22"
    assert api_class.call_args.kwargs["host"] == HOST
    assert api_class.call_args.kwargs["port"] == DEFAULT_PORT
    assert api_class.call_args.kwargs["api_version"] == "v22"


async def test_validate_input_maps_explicit_404_to_unsupported(
    hass: HomeAssistant,
) -> None:
    """Verify explicit API-version 404 errors are rejected as unsupported."""
    api = MagicMock()
    api.async_get_device_info = AsyncMock(
        side_effect=AirlinoApiError("missing", status=404)
    )
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.airlino.config_flow.AirlinoApi",
            return_value=api,
        ),
        pytest.raises(UnsupportedApiVersion),
    ):
        await validate_input(hass, {CONF_HOST: HOST}, api_version="v22")


async def test_validate_input_handles_missing_mac(hass: HomeAssistant) -> None:
    """Verify validation rejects devices without a network MAC address."""
    api = MagicMock()
    api.async_get_device_info = AsyncMock(return_value={})
    api.async_get_network_info = AsyncMock(return_value={})
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.airlino.config_flow.AirlinoApi",
            return_value=api,
        ),
        pytest.raises(CannotIdentify),
    ):
        await validate_input(hass, {CONF_HOST: HOST}, api_version="v22")


async def test_validate_input_rejects_unsupported_version(
    hass: HomeAssistant,
) -> None:
    """Verify explicitly supplied unsupported API versions are rejected."""
    with (
        patch("homeassistant.components.airlino.config_flow.async_get_clientsession"),
        pytest.raises(UnsupportedApiVersion),
    ):
        await validate_input(hass, {CONF_HOST: HOST}, api_version="v18")
