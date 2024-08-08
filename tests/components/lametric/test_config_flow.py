"""Tests for the LaMetric config flow."""

from http import HTTPStatus
from unittest.mock import MagicMock

from demetriek import (
    LaMetricConnectionError,
    LaMetricConnectionTimeoutError,
    LaMetricError,
    Notification,
    NotificationSound,
    Sound,
)
import pytest

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.lametric.const import DOMAIN
from homeassistant.components.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_REAUTH,
    SOURCE_SSDP,
    SOURCE_USER,
)
from homeassistant.const import CONF_API_KEY, CONF_DEVICE, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

SSDP_DISCOVERY_INFO = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="http://127.0.0.1:44057/465d585b-1c05-444a-b14e-6ffb875b46a6/device_description.xml",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "LaMetric Time (LM1245)",
        ATTR_UPNP_SERIAL: "SA110405124500W00BS9",
    },
)


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_cloud_import_flow_multiple_devices(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: MagicMock,
    mock_lametric_cloud: MagicMock,
    mock_lametric: MagicMock,
) -> None:
    """Check a full flow importing from cloud, with multiple devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choice_enter_manual_or_fetch_cloud"
    assert result.get("menu_options") == ["pick_implementation", "manual_entry"]
    flow_id = result["flow_id"]

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result2.get("type") is FlowResultType.EXTERNAL_STEP
    assert result2.get("url") == (
        "https://developer.lametric.com/api/v2/oauth2/authorize"
        "?response_type=code&client_id=client"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=basic+devices_read"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result3 = await hass.config_entries.flow.async_configure(flow_id)

    assert result3.get("type") is FlowResultType.FORM
    assert result3.get("step_id") == "cloud_select_device"

    result4 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_DEVICE: "SA110405124500W00BS9"}
    )

    assert result4.get("type") is FlowResultType.CREATE_ENTRY
    assert result4.get("title") == "Frenck's LaMetric"
    assert result4.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert "result" in result4
    assert result4["result"].unique_id == "SA110405124500W00BS9"

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_cloud_import_flow_single_device(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: MagicMock,
    mock_lametric_cloud: MagicMock,
    mock_lametric: MagicMock,
) -> None:
    """Check a full flow importing from cloud, with a single device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choice_enter_manual_or_fetch_cloud"
    assert result.get("menu_options") == ["pick_implementation", "manual_entry"]
    flow_id = result["flow_id"]

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result2.get("type") is FlowResultType.EXTERNAL_STEP
    assert result2.get("url") == (
        "https://developer.lametric.com/api/v2/oauth2/authorize"
        "?response_type=code&client_id=client"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=basic+devices_read"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    # Stage a single device
    # Should skip step that ask for device selection
    mock_lametric_cloud.devices.return_value = [
        mock_lametric_cloud.devices.return_value[0]
    ]
    result3 = await hass.config_entries.flow.async_configure(flow_id)

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Frenck's LaMetric"
    assert result3.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert "result" in result3
    assert result3["result"].unique_id == "SA110405124500W00BS9"

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_manual(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_lametric: MagicMock,
) -> None:
    """Check a full flow manual entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choice_enter_manual_or_fetch_cloud"
    assert result.get("menu_options") == ["pick_implementation", "manual_entry"]
    flow_id = result["flow_id"]

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "manual_entry"}
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "manual_entry"

    result3 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_HOST: "127.0.0.1", CONF_API_KEY: "mock-api-key"}
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Frenck's LaMetric"
    assert result3.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert "result" in result3
    assert result3["result"].unique_id == "SA110405124500W00BS9"

    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.model.sound == Sound(sound=NotificationSound.WIN)

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_ssdp_with_cloud_import(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: MagicMock,
    mock_lametric_cloud: MagicMock,
    mock_lametric: MagicMock,
) -> None:
    """Check a full flow triggered by SSDP, importing from cloud."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_DISCOVERY_INFO
    )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choice_enter_manual_or_fetch_cloud"
    assert result.get("menu_options") == ["pick_implementation", "manual_entry"]
    flow_id = result["flow_id"]

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result2.get("type") is FlowResultType.EXTERNAL_STEP
    assert result2.get("url") == (
        "https://developer.lametric.com/api/v2/oauth2/authorize"
        "?response_type=code&client_id=client"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=basic+devices_read"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result3 = await hass.config_entries.flow.async_configure(flow_id)

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Frenck's LaMetric"
    assert result3.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert "result" in result3
    assert result3["result"].unique_id == "SA110405124500W00BS9"

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_ssdp_manual_entry(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_lametric: MagicMock,
) -> None:
    """Check a full flow triggered by SSDP, with manual API key entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_DISCOVERY_INFO
    )

    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "choice_enter_manual_or_fetch_cloud"
    assert result.get("menu_options") == ["pick_implementation", "manual_entry"]
    flow_id = result["flow_id"]

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "manual_entry"}
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "manual_entry"

    result3 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_API_KEY: "mock-api-key"}
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Frenck's LaMetric"
    assert result3.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert "result" in result3
    assert result3["result"].unique_id == "SA110405124500W00BS9"

    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (
            SsdpServiceInfo(ssdp_usn="mock_usn", ssdp_st="mock_st", upnp={}),
            "invalid_discovery_info",
        ),
        (
            SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                ssdp_location="http://169.254.0.1:44057/465d585b-1c05-444a-b14e-6ffb875b46a6/device_description.xml",
                upnp={
                    ATTR_UPNP_SERIAL: "SA110405124500W00BS9",
                },
            ),
            "link_local_address",
        ),
    ],
)
async def test_ssdp_abort_invalid_discovery(
    hass: HomeAssistant, data: SsdpServiceInfo, reason: str
) -> None:
    """Check a full flow triggered by SSDP, with manual API key entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=data
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == reason


@pytest.mark.usefixtures("current_request_with_host")
async def test_cloud_import_updates_existing_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_lametric_cloud: MagicMock,
    mock_lametric: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cloud importing existing device updates existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    await hass.config_entries.flow.async_configure(flow_id)

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_DEVICE: "SA110405124500W00BS9"}
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 0


async def test_manual_updates_existing_entry(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding existing device updates existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "manual_entry"}
    )

    result3 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_HOST: "127.0.0.1", CONF_API_KEY: "mock-api-key"}
    )

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }

    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 0


async def test_discovery_updates_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery of existing device updates entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_DISCOVERY_INFO
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-from-fixture",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }


@pytest.mark.usefixtures("current_request_with_host")
async def test_cloud_abort_no_devices(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_lametric_cloud: MagicMock,
) -> None:
    """Test cloud importing aborts when account has no devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    # Stage there are no devices
    mock_lametric_cloud.devices.return_value = []
    result2 = await hass.config_entries.flow.async_configure(flow_id)

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "no_devices"

    assert len(mock_lametric_cloud.devices.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (LaMetricConnectionTimeoutError, "cannot_connect"),
        (LaMetricConnectionError, "cannot_connect"),
        (LaMetricError, "unknown"),
        (RuntimeError, "unknown"),
    ],
)
async def test_manual_errors(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    mock_setup_entry: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test adding existing device updates existing entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "manual_entry"}
    )

    mock_lametric.device.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_HOST: "127.0.0.1", CONF_API_KEY: "mock-api-key"}
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "manual_entry"
    assert result2.get("errors") == {"base": reason}

    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0

    mock_lametric.device.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_HOST: "127.0.0.1", CONF_API_KEY: "mock-api-key"}
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Frenck's LaMetric"
    assert result3.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert "result" in result3
    assert result3["result"].unique_id == "SA110405124500W00BS9"

    assert len(mock_lametric.device.mock_calls) == 2
    assert len(mock_lametric.notify.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (LaMetricConnectionTimeoutError, "cannot_connect"),
        (LaMetricConnectionError, "cannot_connect"),
        (LaMetricError, "unknown"),
        (RuntimeError, "unknown"),
    ],
)
async def test_cloud_errors(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: MagicMock,
    mock_lametric_cloud: MagicMock,
    mock_lametric: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test adding existing device updates existing entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    await hass.config_entries.flow.async_configure(flow_id)

    mock_lametric.device.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_DEVICE: "SA110405124500W00BS9"}
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "cloud_select_device"
    assert result2.get("errors") == {"base": reason}

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0

    mock_lametric.device.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_DEVICE: "SA110405124500W00BS9"}
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Frenck's LaMetric"
    assert result3.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert "result" in result3
    assert result3["result"].unique_id == "SA110405124500W00BS9"

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 2
    assert len(mock_lametric.notify.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_updates_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery updates config entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="lametric",
            ip="127.0.0.42",
            macaddress="aabbccddeeff",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry.data == {
        CONF_API_KEY: "mock-from-fixture",
        CONF_HOST: "127.0.0.42",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }


async def test_dhcp_unknown_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unknown DHCP discovery aborts flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="lametric",
            ip="127.0.0.42",
            macaddress="aabbccddee00",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unknown"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_cloud_import(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_lametric_cloud: MagicMock,
    mock_lametric: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow importing api keys from the cloud."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result2 = await hass.config_entries.flow.async_configure(flow_id)

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_cloud_abort_device_not_found(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_lametric_cloud: MagicMock,
    mock_lametric: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow importing api keys from the cloud."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id="UKNOWN_DEVICE")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(
        "https://developer.lametric.com/api/v2/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result2 = await hass.config_entries.flow.async_configure(flow_id)

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_device_not_found"

    assert len(mock_lametric_cloud.devices.mock_calls) == 1
    assert len(mock_lametric.device.mock_calls) == 0
    assert len(mock_lametric.notify.mock_calls) == 0


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_manual(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with manual entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "manual_entry"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_API_KEY: "mock-api-key"}
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }

    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize("device_fixture", ["device_sa5"])
async def test_reauth_manual_sky(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with manual entry for LaMetric Sky."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "manual_entry"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_API_KEY: "mock-api-key"}
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_API_KEY: "mock-api-key",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }

    assert len(mock_lametric.device.mock_calls) == 1
    assert len(mock_lametric.notify.mock_calls) == 1

    notification: Notification = mock_lametric.notify.mock_calls[0][2]["notification"]
    assert notification.model.sound is None
