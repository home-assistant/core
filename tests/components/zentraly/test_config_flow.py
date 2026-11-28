"""Tests for the Zentraly config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from zentraly import ZentralyAuthenticationError, ZentralyConnectionError

from homeassistant import config_entries
from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import DEVICE_ID, HOST, PASSWORD, PORT

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_api")
NEW_HOST = "192.168.1.43"
NEW_PORT = 12346


def _zeroconf_info(
    host: str = HOST, port: int = PORT, device_id: str = DEVICE_ID
) -> ZeroconfServiceInfo:
    """Return mock Zentraly Zeroconf discovery information."""
    address = ip_address(host)
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        hostname=f"{device_id}.local.",
        name=f"{device_id}._zentraly._tcp.local.",
        port=port,
        properties={},
        type="_zentraly._tcp.local.",
    )


async def test_zeroconf_auth_success(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Discover, authenticate and create a uniquely identified entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": CONF_PASSWORD,
            "required": True,
            "secret": True,
            "selector": {
                "text": {
                    "type": "password",
                    "autocomplete": "current-password",
                    "multiline": False,
                    "multiple": False,
                }
            },
        }
    ]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_ID
    assert result["result"].unique_id == DEVICE_ID
    assert result["data"] == {
        "host": HOST,
        "port": PORT,
        "device_id": DEVICE_ID,
        "password": PASSWORD,
        "mac": mock_api.async_validate_password.return_value,
    }
    mock_setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    "device_id",
    [
        "UNKNOWN",
        "ZTTWZ0100000001",
        "ZTBIN0100000001",
        "ZTREA0100000001",
        "ZTEIM0100000001",
        "ZTIKD0100000001",
        "ZTIKS0100000001",
    ],
)
async def test_zeroconf_unsupported_device(hass: HomeAssistant, device_id: str) -> None:
    """Ignore devices outside the initial thermostat scope."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(device_id=device_id),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        pytest.param(ZentralyAuthenticationError, "invalid_auth", id="authentication"),
        pytest.param(ZentralyConnectionError, "cannot_connect", id="connection"),
    ],
)
async def test_auth_recovery(
    hass: HomeAssistant, mock_api: MagicMock, error: type[Exception], key: str
) -> None:
    """A failed validation remains recoverable without restarting discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )
    mock_api.async_validate_password.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "wrong-password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": key}
    mock_api.async_validate_password.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID
    assert result["data"][CONF_PASSWORD] == PASSWORD


@pytest.mark.parametrize(
    ("host", "port"),
    [
        pytest.param(NEW_HOST, NEW_PORT, id="changed"),
        pytest.param(HOST, PORT, id="unchanged"),
    ],
)
async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, host: str, port: int
) -> None:
    """Rediscovery updates only the network endpoint of an existing entry."""
    data = dict(mock_config_entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(host=host, port=port),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {**data, CONF_HOST: host, CONF_PORT: port}


async def _start_manual_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Choose manual setup without offering child setup in the initial delivery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["manual"]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "manual"}
    )


async def test_user_setup_without_discoveries(
    hass: HomeAssistant, mock_api: MagicMock, mock_api_class: MagicMock
) -> None:
    """Validate and create a manual entry without a discovery announcement."""
    result = await _start_manual_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert [field["name"] for field in fields] == [
        CONF_HOST,
        CONF_DEVICE_ID,
        CONF_PASSWORD,
    ]
    assert fields[2]["secret"] is True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOST,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_ID
    assert result["result"].unique_id == DEVICE_ID
    assert result["data"] == {
        "host": HOST,
        "port": 80,
        "device_id": DEVICE_ID,
        "password": PASSWORD,
        "mac": mock_api.async_validate_password.return_value,
    }
    assert mock_api_class.call_args.kwargs[CONF_PORT] == 80


@pytest.mark.parametrize(
    ("error", "key"),
    [
        pytest.param(ZentralyAuthenticationError, "invalid_auth", id="authentication"),
        pytest.param(ZentralyConnectionError, "cannot_connect", id="connection"),
    ],
)
async def test_user_auth_recovery(
    hass: HomeAssistant, mock_api: MagicMock, error: type[Exception], key: str
) -> None:
    """Manual setup can recover from authentication and connection failures."""
    result = await _start_manual_flow(hass)
    user_input = {CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}
    mock_api.async_validate_password.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": key}
    mock_api.async_validate_password.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID


async def test_user_unsupported_device_recovery(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Correct an unsupported identifier without restarting manual setup."""
    result = await _start_manual_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOST,
            CONF_DEVICE_ID: "UNKNOWN",
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE_ID: "unsupported_device"}
    mock_api.async_validate_password.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOST,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID


@pytest.mark.parametrize(
    "host",
    ["", "192.168.1.999", "zentraly.local", "http://192.168.1.42", "2001:db8::1"],
)
async def test_user_invalid_ip_recovery(
    hass: HomeAssistant, mock_api: MagicMock, host: str
) -> None:
    """Reject invalid IP input before connecting and allow it to be corrected."""
    result = await _start_manual_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: host,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    mock_api.async_validate_password.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOST,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID


async def test_user_setup_with_pending_discovery(hass: HomeAssistant) -> None:
    """Manual setup succeeds and removes the pending discovery for the same device."""
    discovery = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )
    assert discovery["type"] is FlowResultType.FORM
    assert discovery["step_id"] == "auth"
    result = await _start_manual_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOST,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    ("device_id", "validation_count"),
    [
        pytest.param(DEVICE_ID, 0, id="device-id"),
        pytest.param("ZTTIN0100000632", 1, id="mac-with-different-device-id"),
    ],
)
async def test_user_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_id: str,
    validation_count: int,
) -> None:
    """Manual setup cannot duplicate or change the endpoint of an existing device."""
    original_data = dict(mock_config_entry.data)
    result = await _start_manual_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOST,
            CONF_DEVICE_ID: device_id,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == original_data
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_api.async_validate_password.await_count == validation_count


async def test_zeroconf_already_configured_mac(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Discovery cannot create another entry for a MAC already installed."""
    original_data = dict(mock_config_entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(device_id="ZTTIN0100000632"),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == original_data
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_user_add_another_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """A different device ID and MAC can be installed alongside an existing device."""
    original_data = dict(mock_config_entry.data)
    mock_api.async_validate_password.return_value = "001122334455"
    result = await _start_manual_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOST,
            CONF_DEVICE_ID: "ZTTIN0100000632",
            CONF_PASSWORD: PASSWORD,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "ZTTIN0100000632"
    assert mock_config_entry.data == original_data
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
