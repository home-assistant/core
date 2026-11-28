"""Test the AirLino config flow."""

from ipaddress import IPv4Address
from typing import Any
from unittest.mock import MagicMock

from airlino_api import DEFAULT_PORT, AirlinoApiConnectionError, AirlinoApiError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.airlino.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import HOST, MAC

DISCOVERED_HOST = "192.0.2.42"


def _discovery_info(
    properties: dict[str, Any] | None = None, port: int | None = DEFAULT_PORT
) -> ZeroconfServiceInfo:
    """Build service information for a discovered AirLino."""
    address = IPv4Address(DISCOVERED_HOST)
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        port=port,
        hostname="AirLinopro-12AB.local.",
        type="_dockset._tcp.local.",
        name="Livingroom._dockset._tcp.local.",
        properties={"api": "v22"} if properties is None else properties,
    )


def _api_versions(mock_airlino_api_class: MagicMock) -> list[str]:
    """Return the API versions the client was created with, in order."""
    return [
        call.kwargs["api_version"] for call in mock_airlino_api_class.call_args_list
    ]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant, mock_airlino_api_class: MagicMock
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["result"].unique_id == MAC
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_API_VERSION: "v22",
    }
    assert _api_versions(mock_airlino_api_class) == ["v22"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_custom_port(
    hass: HomeAssistant, mock_airlino_api_class: MagicMock
) -> None:
    """Test the user flow with a non-default port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: 9000}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MAC
    assert result["data"][CONF_PORT] == 9000
    assert mock_airlino_api_class.call_args.kwargs["port"] == 9000


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("network_info", "unique_id"),
    [
        pytest.param({"eth": {"mac": "00-23-B1-A4-35-9E"}}, MAC, id="eth"),
        pytest.param(
            {"wlan": {"mac": "00:23:b1:66:ab:94", "ssid": "AirLino-WLAN"}},
            "00:23:b1:66:ab:94",
            id="wlan",
        ),
        pytest.param(
            {"eth": {}, "wlan": {"mac": "00:23:b1:66:ab:94"}},
            "00:23:b1:66:ab:94",
            id="empty_eth",
        ),
    ],
)
async def test_user_flow_unique_id_from_active_interface(
    hass: HomeAssistant,
    mock_airlino_api: MagicMock,
    network_info: dict[str, Any],
    unique_id: str,
) -> None:
    """Test the unique ID is the normalized MAC of the active interface."""
    mock_airlino_api.async_get_network_info.return_value = network_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == unique_id


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_falls_back_to_older_api_version(
    hass: HomeAssistant,
    mock_airlino_api_class: MagicMock,
    mock_airlino_api: MagicMock,
) -> None:
    """Test older API versions are probed until one responds."""
    mock_airlino_api.async_get_device_info.side_effect = [
        AirlinoApiError("missing", status=404),
        AirlinoApiError("failed"),
        {"devicename": "Living room"},
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MAC
    assert result["data"][CONF_API_VERSION] == "v20"
    assert _api_versions(mock_airlino_api_class) == ["v22", "v21", "v20"]


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(
            AirlinoApiConnectionError("offline"), "cannot_connect", id="offline"
        ),
        pytest.param(
            AirlinoApiError("failed", status=500), "cannot_connect", id="http_error"
        ),
        pytest.param(
            AirlinoApiError("missing", status=404),
            "unsupported_api_version",
            id="unsupported_api_version",
        ),
        pytest.param(RuntimeError("unexpected"), "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_airlino_api: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the user flow shows errors and recovers from them."""
    mock_airlino_api.async_get_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_airlino_api.async_get_device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MAC


@pytest.mark.usefixtures("mock_airlino_api")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the user flow aborts for an already configured device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_airlino_api")
async def test_user_flow_aborts_while_discovery_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test the user flow aborts while the device is being discovered."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow(
    hass: HomeAssistant, mock_airlino_api_class: MagicMock
) -> None:
    """Test discovery uses the announced API version."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"name": "Living room"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["result"].unique_id == MAC
    assert result["data"] == {
        CONF_HOST: DISCOVERED_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_API_VERSION: "v22",
    }
    assert _api_versions(mock_airlino_api_class) == ["v22"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_probes_api_version_without_txt_record(
    hass: HomeAssistant,
    mock_airlino_api_class: MagicMock,
    mock_airlino_api: MagicMock,
) -> None:
    """Test discovery probes the API version when it is not announced."""
    mock_airlino_api.async_get_device_info.side_effect = [
        AirlinoApiError("missing", status=404),
        {"devicename": "Living room"},
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(properties={}, port=None),
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MAC
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert result["data"][CONF_API_VERSION] == "v21"
    assert _api_versions(mock_airlino_api_class) == ["v22", "v21"]


@pytest.mark.parametrize(
    ("properties", "exception", "reason"),
    [
        pytest.param({"api": "v18"}, None, "unsupported_api_version", id="too_old"),
        pytest.param(
            {"api": "invalid"}, None, "unsupported_api_version", id="invalid_version"
        ),
        pytest.param(
            {"api": "v22"},
            AirlinoApiError("missing", status=404),
            "unsupported_api_version",
            id="not_found",
        ),
        pytest.param(
            {"api": "v22"},
            AirlinoApiConnectionError("offline"),
            "cannot_connect",
            id="offline",
        ),
        pytest.param(
            {"api": "v22"},
            AirlinoApiError("failed", status=500),
            "cannot_connect",
            id="http_error",
        ),
        pytest.param(
            {"api": "v22"}, RuntimeError("unexpected"), "unknown", id="unknown"
        ),
    ],
)
async def test_zeroconf_flow_aborts(
    hass: HomeAssistant,
    mock_airlino_api: MagicMock,
    properties: dict[str, Any],
    exception: Exception | None,
    reason: str,
) -> None:
    """Test discovery aborts for unsupported or unreachable devices."""
    mock_airlino_api.async_get_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(properties=properties),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_airlino_api")
async def test_zeroconf_flow_updates_configured_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery updates the connection details of a configured device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(port=9000),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == DISCOVERED_HOST
    assert mock_config_entry.data[CONF_PORT] == 9000
