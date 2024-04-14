"""Test UniFi Network."""

from copy import deepcopy
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import Mock, patch

import aiounifi
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_SITE_ID,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DEFAULT_ALLOW_BANDWIDTH_SENSORS,
    DEFAULT_ALLOW_UPTIME_SENSORS,
    DEFAULT_DETECTION_TIME,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_DEVICES,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DOMAIN as UNIFI_DOMAIN,
    UNIFI_WIRELESS_CLIENTS,
)
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.unifi.hub import get_unifi_api
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

DEFAULT_CONFIG_ENTRY_ID = "1"
DEFAULT_HOST = "1.2.3.4"
DEFAULT_SITE = "site_id"

CONTROLLER_HOST = {
    "hostname": "controller_host",
    "ip": DEFAULT_HOST,
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "10:00:00:00:00:01",
    "name": "Controller host",
    "oui": "Producer",
    "sw_mac": "00:00:00:00:01:01",
    "sw_port": 1,
    "wired-rx_bytes": 1234000000,
    "wired-tx_bytes": 5678000000,
    "uptime": 1562600160,
}

ENTRY_CONFIG = {
    CONF_HOST: DEFAULT_HOST,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 1234,
    CONF_SITE_ID: DEFAULT_SITE,
    CONF_VERIFY_SSL: False,
}
ENTRY_OPTIONS = {}

CONFIGURATION = []

SITE = [{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}]

SYSTEM_INFORMATION = [
    {
        "anonymous_controller_id": "24f81231-a456-4c32-abcd-f5612345385f",
        "build": "atag_7.4.162_21057",
        "console_display_version": "3.1.15",
        "hostname": "UDMP",
        "name": "UDMP",
        "previous_version": "7.4.156",
        "timezone": "Europe/Stockholm",
        "ubnt_device_type": "UDMPRO",
        "udm_version": "3.0.20.9281",
        "update_available": False,
        "update_downloaded": False,
        "uptime": 1196290,
        "version": "7.4.162",
    }
]


def mock_default_unifi_requests(
    aioclient_mock,
    host,
    site_id,
    sites=None,
    clients_response=None,
    clients_all_response=None,
    devices_response=None,
    dpiapp_response=None,
    dpigroup_response=None,
    port_forward_response=None,
    system_information_response=None,
    wlans_response=None,
):
    """Mock default UniFi requests responses."""
    aioclient_mock.get(f"https://{host}:1234", status=302)  # Check UniFi OS

    aioclient_mock.post(
        f"https://{host}:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"https://{host}:1234/api/self/sites",
        json={"data": sites or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/stat/sta",
        json={"data": clients_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/rest/user",
        json={"data": clients_all_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/stat/device",
        json={"data": devices_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/rest/dpiapp",
        json={"data": dpiapp_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/rest/dpigroup",
        json={"data": dpigroup_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/rest/portforward",
        json={"data": port_forward_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/stat/sysinfo",
        json={"data": system_information_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/api/s/{site_id}/rest/wlanconf",
        json={"data": wlans_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/v2/api/site/{site_id}/trafficroutes",
        json=[{}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"https://{host}:1234/v2/api/site/{site_id}/trafficrules",
        json=[{}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )


async def setup_unifi_integration(
    hass,
    aioclient_mock=None,
    *,
    config=ENTRY_CONFIG,
    options=ENTRY_OPTIONS,
    sites=SITE,
    clients_response=None,
    clients_all_response=None,
    devices_response=None,
    dpiapp_response=None,
    dpigroup_response=None,
    port_forward_response=None,
    system_information_response=None,
    wlans_response=None,
    known_wireless_clients=None,
    unique_id="1",
    config_entry_id=DEFAULT_CONFIG_ENTRY_ID,
):
    """Create the UniFi Network instance."""
    assert await async_setup_component(hass, UNIFI_DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data=deepcopy(config),
        options=deepcopy(options),
        unique_id=unique_id,
        entry_id=config_entry_id,
        version=1,
    )
    config_entry.add_to_hass(hass)

    if known_wireless_clients:
        hass.data[UNIFI_WIRELESS_CLIENTS].wireless_clients.update(
            known_wireless_clients
        )

    if aioclient_mock:
        mock_default_unifi_requests(
            aioclient_mock,
            host=config_entry.data[CONF_HOST],
            site_id=config_entry.data[CONF_SITE_ID],
            sites=sites,
            clients_response=clients_response,
            clients_all_response=clients_all_response,
            devices_response=devices_response,
            dpiapp_response=dpiapp_response,
            dpigroup_response=dpigroup_response,
            port_forward_response=port_forward_response,
            system_information_response=system_information_response,
            wlans_response=wlans_response,
        )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    if config_entry.entry_id not in hass.data[UNIFI_DOMAIN]:
        return None

    return config_entry


async def test_hub_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as forward_entry_setup:
        config_entry = await setup_unifi_integration(
            hass, aioclient_mock, system_information_response=SYSTEM_INFORMATION
        )
        hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    entry = hub.config.entry
    assert len(forward_entry_setup.mock_calls) == 1
    assert forward_entry_setup.mock_calls[0][1] == (
        entry,
        [
            BUTTON_DOMAIN,
            TRACKER_DOMAIN,
            IMAGE_DOMAIN,
            SENSOR_DOMAIN,
            SWITCH_DOMAIN,
            UPDATE_DOMAIN,
        ],
    )

    assert hub.config.host == ENTRY_CONFIG[CONF_HOST]
    assert hub.is_admin == (SITE[0]["role"] == "admin")

    assert hub.config.option_allow_bandwidth_sensors == DEFAULT_ALLOW_BANDWIDTH_SENSORS
    assert hub.config.option_allow_uptime_sensors == DEFAULT_ALLOW_UPTIME_SENSORS
    assert isinstance(hub.config.option_block_clients, list)
    assert hub.config.option_track_clients == DEFAULT_TRACK_CLIENTS
    assert hub.config.option_track_devices == DEFAULT_TRACK_DEVICES
    assert hub.config.option_track_wired_clients == DEFAULT_TRACK_WIRED_CLIENTS
    assert hub.config.option_detection_time == timedelta(seconds=DEFAULT_DETECTION_TIME)
    assert isinstance(hub.config.option_ssid_filter, set)

    assert hub.signal_reachable == "unifi-reachable-1"
    assert hub.signal_options_update == "unifi-options-1"
    assert hub.signal_heartbeat_missed == "unifi-heartbeat-missed"

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(UNIFI_DOMAIN, config_entry.unique_id)},
    )

    assert device_entry.sw_version == "7.4.162"


async def test_hub_not_accessible(hass: HomeAssistant) -> None:
    """Retry to login gets scheduled when connection fails."""
    with patch(
        "homeassistant.components.unifi.hub.get_unifi_api",
        side_effect=CannotConnect,
    ):
        await setup_unifi_integration(hass)
    assert hass.data[UNIFI_DOMAIN] == {}


async def test_hub_trigger_reauth_flow(hass: HomeAssistant) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with (
        patch(
            "homeassistant.components.unifi.get_unifi_api",
            side_effect=AuthenticationRequired,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        await setup_unifi_integration(hass)
        mock_flow_init.assert_called_once()
    assert hass.data[UNIFI_DOMAIN] == {}


async def test_hub_unknown_error(hass: HomeAssistant) -> None:
    """Unknown errors are handled."""
    with patch(
        "homeassistant.components.unifi.hub.get_unifi_api",
        side_effect=Exception,
    ):
        await setup_unifi_integration(hass)
    assert hass.data[UNIFI_DOMAIN] == {}


async def test_config_entry_updated(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Calling reset when the entry has been setup."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    event_call = Mock()
    unsub = async_dispatcher_connect(hass, hub.signal_options_update, event_call)

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_TRACK_CLIENTS: False, CONF_TRACK_DEVICES: False}
    )
    await hass.async_block_till_done()

    assert config_entry.options[CONF_TRACK_CLIENTS] is False
    assert config_entry.options[CONF_TRACK_DEVICES] is False

    event_call.assert_called_once()

    unsub()


async def test_reset_after_successful_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Calling reset when the entry has been setup."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    result = await hub.async_reset()
    await hass.async_block_till_done()

    assert result is True


async def test_reset_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Calling reset when the entry has been setup can return false."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=False,
    ):
        result = await hub.async_reset()
        await hass.async_block_till_done()

    assert result is False


async def test_connection_state_signalling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_device_registry,
    websocket_mock,
) -> None:
    """Verify connection statesignalling and connection state are working."""
    client = {
        "hostname": "client",
        "ip": "10.0.0.1",
        "is_wired": True,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "mac": "00:00:00:00:00:01",
    }
    await setup_unifi_integration(hass, aioclient_mock, clients_response=[client])

    # Controller is connected
    assert hass.states.get("device_tracker.client").state == "home"

    await websocket_mock.disconnect()
    # Controller is disconnected
    assert hass.states.get("device_tracker.client").state == "unavailable"

    await websocket_mock.reconnect()
    # Controller is once again connected
    assert hass.states.get("device_tracker.client").state == "home"


async def test_reconnect_mechanism(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, websocket_mock
) -> None:
    """Verify reconnect prints only on first reconnection try."""
    await setup_unifi_integration(hass, aioclient_mock)

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"https://{DEFAULT_HOST}:1234/", status=HTTPStatus.BAD_GATEWAY)

    await websocket_mock.disconnect()
    assert aioclient_mock.call_count == 0

    await websocket_mock.reconnect(fail=True)
    assert aioclient_mock.call_count == 1

    await websocket_mock.reconnect(fail=True)
    assert aioclient_mock.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError,
        aiounifi.BadGateway,
        aiounifi.ServiceUnavailable,
        aiounifi.AiounifiException,
    ],
)
async def test_reconnect_mechanism_exceptions(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, websocket_mock, exception
) -> None:
    """Verify async_reconnect calls expected methods."""
    await setup_unifi_integration(hass, aioclient_mock)

    with (
        patch("aiounifi.Controller.login", side_effect=exception),
        patch(
            "homeassistant.components.unifi.hub.hub.UnifiWebsocket.reconnect"
        ) as mock_reconnect,
    ):
        await websocket_mock.disconnect()

        await websocket_mock.reconnect()
        mock_reconnect.assert_called_once()


async def test_get_unifi_api(hass: HomeAssistant) -> None:
    """Successful call."""
    with patch("aiounifi.Controller.login", return_value=True):
        assert await get_unifi_api(hass, ENTRY_CONFIG)


async def test_get_unifi_api_verify_ssl_false(hass: HomeAssistant) -> None:
    """Successful call with verify ssl set to false."""
    hub_data = dict(ENTRY_CONFIG)
    hub_data[CONF_VERIFY_SSL] = False
    with patch("aiounifi.Controller.login", return_value=True):
        assert await get_unifi_api(hass, hub_data)


@pytest.mark.parametrize(
    ("side_effect", "raised_exception"),
    [
        (TimeoutError, CannotConnect),
        (aiounifi.BadGateway, CannotConnect),
        (aiounifi.Forbidden, CannotConnect),
        (aiounifi.ServiceUnavailable, CannotConnect),
        (aiounifi.RequestError, CannotConnect),
        (aiounifi.ResponseError, CannotConnect),
        (aiounifi.Unauthorized, AuthenticationRequired),
        (aiounifi.LoginRequired, AuthenticationRequired),
        (aiounifi.AiounifiException, AuthenticationRequired),
    ],
)
async def test_get_unifi_api_fails_to_connect(
    hass: HomeAssistant, side_effect, raised_exception
) -> None:
    """Check that get_unifi_api can handle UniFi Network being unavailable."""
    with (
        patch("aiounifi.Controller.login", side_effect=side_effect),
        pytest.raises(raised_exception),
    ):
        await get_unifi_api(hass, ENTRY_CONFIG)
