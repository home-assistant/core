"""Test UniFi Controller."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock, patch

import aiounifi
from aiounifi.websocket import STATE_DISCONNECTED, STATE_RUNNING
import pytest

from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_CONTROLLER,
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
from homeassistant.components.unifi.controller import (
    PLATFORMS,
    RETRY_TIMER,
    get_controller,
)
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

DEFAULT_CONFIG_ENTRY_ID = 1
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

CONTROLLER_DATA = {
    CONF_HOST: DEFAULT_HOST,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 1234,
    CONF_SITE_ID: DEFAULT_SITE,
    CONF_VERIFY_SSL: False,
}

ENTRY_CONFIG = {**CONTROLLER_DATA, CONF_CONTROLLER: CONTROLLER_DATA}
ENTRY_OPTIONS = {}

CONFIGURATION = []

SITE = [{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}]
DESCRIPTION = [{"name": "username", "site_name": "site_id", "site_role": "admin"}]


def mock_default_unifi_requests(
    aioclient_mock,
    host,
    site_id,
    sites=None,
    description=None,
    clients_response=None,
    clients_all_response=None,
    devices_response=None,
    dpiapp_response=None,
    dpigroup_response=None,
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
        f"https://{host}:1234/api/s/{site_id}/self",
        json={"data": description or [], "meta": {"rc": "ok"}},
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
        f"https://{host}:1234/api/s/{site_id}/rest/wlanconf",
        json={"data": wlans_response or [], "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )


async def setup_unifi_integration(
    hass,
    aioclient_mock=None,
    *,
    config=ENTRY_CONFIG,
    options=ENTRY_OPTIONS,
    sites=SITE,
    site_description=DESCRIPTION,
    clients_response=None,
    clients_all_response=None,
    devices_response=None,
    dpiapp_response=None,
    dpigroup_response=None,
    wlans_response=None,
    known_wireless_clients=None,
    controllers=None,
    unique_id="1",
):
    """Create the UniFi controller."""
    assert await async_setup_component(hass, UNIFI_DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data=deepcopy(config),
        options=deepcopy(options),
        unique_id=unique_id,
        entry_id=DEFAULT_CONFIG_ENTRY_ID,
        version=1,
    )
    config_entry.add_to_hass(hass)

    if known_wireless_clients:
        hass.data[UNIFI_WIRELESS_CLIENTS].update_data(
            known_wireless_clients, config_entry
        )

    if aioclient_mock:
        mock_default_unifi_requests(
            aioclient_mock,
            host=config_entry.data[CONF_HOST],
            site_id=config_entry.data[CONF_SITE_ID],
            sites=sites,
            description=site_description,
            clients_response=clients_response,
            clients_all_response=clients_all_response,
            devices_response=devices_response,
            dpiapp_response=dpiapp_response,
            dpigroup_response=dpigroup_response,
            wlans_response=wlans_response,
        )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    if config_entry.entry_id not in hass.data[UNIFI_DOMAIN]:
        return None

    return config_entry


async def test_controller_setup(hass, aioclient_mock):
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        config_entry = await setup_unifi_integration(hass, aioclient_mock)
        controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    entry = controller.config_entry
    assert len(forward_entry_setup.mock_calls) == len(PLATFORMS)
    assert forward_entry_setup.mock_calls[0][1] == (entry, TRACKER_DOMAIN)
    assert forward_entry_setup.mock_calls[1][1] == (entry, SENSOR_DOMAIN)
    assert forward_entry_setup.mock_calls[2][1] == (entry, SWITCH_DOMAIN)

    assert controller.host == CONTROLLER_DATA[CONF_HOST]
    assert controller.site == CONTROLLER_DATA[CONF_SITE_ID]
    assert controller.site_name == SITE[0]["desc"]
    assert controller.site_role == SITE[0]["role"]

    assert controller.option_allow_bandwidth_sensors == DEFAULT_ALLOW_BANDWIDTH_SENSORS
    assert controller.option_allow_uptime_sensors == DEFAULT_ALLOW_UPTIME_SENSORS
    assert isinstance(controller.option_block_clients, list)
    assert controller.option_track_clients == DEFAULT_TRACK_CLIENTS
    assert controller.option_track_devices == DEFAULT_TRACK_DEVICES
    assert controller.option_track_wired_clients == DEFAULT_TRACK_WIRED_CLIENTS
    assert controller.option_detection_time == timedelta(seconds=DEFAULT_DETECTION_TIME)
    assert isinstance(controller.option_ssid_filter, set)

    assert controller.mac is None

    assert controller.signal_reachable == "unifi-reachable-1"
    assert controller.signal_update == "unifi-update-1"
    assert controller.signal_remove == "unifi-remove-1"
    assert controller.signal_options_update == "unifi-options-1"
    assert controller.signal_heartbeat_missed == "unifi-heartbeat-missed"


async def test_controller_mac(hass, aioclient_mock):
    """Test that it is possible to identify controller mac."""
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=[CONTROLLER_HOST]
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    assert controller.mac == CONTROLLER_HOST["mac"]


async def test_controller_not_accessible(hass):
    """Retry to login gets scheduled when connection fails."""
    with patch(
        "homeassistant.components.unifi.controller.get_controller",
        side_effect=CannotConnect,
    ):
        await setup_unifi_integration(hass)
    assert hass.data[UNIFI_DOMAIN] == {}


async def test_controller_trigger_reauth_flow(hass):
    """Failed authentication trigger a reauthentication flow."""
    with patch(
        "homeassistant.components.unifi.controller.get_controller",
        side_effect=AuthenticationRequired,
    ), patch.object(hass.config_entries.flow, "async_init") as mock_flow_init:
        await setup_unifi_integration(hass)
        mock_flow_init.assert_called_once()
    assert hass.data[UNIFI_DOMAIN] == {}


async def test_controller_unknown_error(hass):
    """Unknown errors are handled."""
    with patch(
        "homeassistant.components.unifi.controller.get_controller",
        side_effect=Exception,
    ):
        await setup_unifi_integration(hass)
    assert hass.data[UNIFI_DOMAIN] == {}


async def test_config_entry_updated(hass, aioclient_mock):
    """Calling reset when the entry has been setup."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    event_call = Mock()
    unsub = async_dispatcher_connect(hass, controller.signal_options_update, event_call)

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_TRACK_CLIENTS: False, CONF_TRACK_DEVICES: False}
    )
    await hass.async_block_till_done()

    assert config_entry.options[CONF_TRACK_CLIENTS] is False
    assert config_entry.options[CONF_TRACK_DEVICES] is False

    event_call.assert_called_once()

    unsub()


async def test_reset_after_successful_setup(hass, aioclient_mock):
    """Calling reset when the entry has been setup."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    result = await controller.async_reset()
    await hass.async_block_till_done()

    assert result is True


async def test_reset_fails(hass, aioclient_mock):
    """Calling reset when the entry has been setup can return false."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=False,
    ):
        result = await controller.async_reset()
        await hass.async_block_till_done()

    assert result is False


async def test_connection_state_signalling(hass, aioclient_mock, mock_unifi_websocket):
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

    mock_unifi_websocket(state=STATE_DISCONNECTED)
    await hass.async_block_till_done()

    # Controller is disconnected
    assert hass.states.get("device_tracker.client").state == "unavailable"

    mock_unifi_websocket(state=STATE_RUNNING)
    await hass.async_block_till_done()

    # Controller is once again connected
    assert hass.states.get("device_tracker.client").state == "home"


async def test_wireless_client_event_calls_update_wireless_devices(
    hass, aioclient_mock, mock_unifi_websocket
):
    """Call update_wireless_devices method when receiving wireless client event."""
    await setup_unifi_integration(hass, aioclient_mock)

    with patch(
        "homeassistant.components.unifi.controller.UniFiController.update_wireless_clients",
        return_value=None,
    ) as wireless_clients_mock:
        mock_unifi_websocket(
            data={
                "meta": {"rc": "ok", "message": "events"},
                "data": [
                    {
                        "datetime": "2020-01-20T19:37:04Z",
                        "key": aiounifi.events.WIRELESS_CLIENT_CONNECTED,
                        "msg": "User[11:22:33:44:55:66] has connected to WLAN",
                        "time": 1579549024893,
                    }
                ],
            },
        )

        assert wireless_clients_mock.assert_called_once


async def test_reconnect_mechanism(hass, aioclient_mock, mock_unifi_websocket):
    """Verify reconnect prints only on first reconnection try."""
    await setup_unifi_integration(hass, aioclient_mock)

    aioclient_mock.clear_requests()
    aioclient_mock.post(f"https://{DEFAULT_HOST}:1234/api/login", status=502)

    mock_unifi_websocket(state=STATE_DISCONNECTED)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 0

    new_time = dt_util.utcnow() + timedelta(seconds=RETRY_TIMER)
    async_fire_time_changed(hass, new_time)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1

    new_time = dt_util.utcnow() + timedelta(seconds=RETRY_TIMER)
    async_fire_time_changed(hass, new_time)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        asyncio.TimeoutError,
        aiounifi.BadGateway,
        aiounifi.ServiceUnavailable,
        aiounifi.AiounifiException,
    ],
)
async def test_reconnect_mechanism_exceptions(
    hass, aioclient_mock, mock_unifi_websocket, exception
):
    """Verify async_reconnect calls expected methods."""
    await setup_unifi_integration(hass, aioclient_mock)

    with patch("aiounifi.Controller.login", side_effect=exception), patch(
        "homeassistant.components.unifi.controller.UniFiController.reconnect"
    ) as mock_reconnect:
        mock_unifi_websocket(state=STATE_DISCONNECTED)
        await hass.async_block_till_done()

        new_time = dt_util.utcnow() + timedelta(seconds=RETRY_TIMER)
        async_fire_time_changed(hass, new_time)
        mock_reconnect.assert_called_once()


async def test_get_controller(hass):
    """Successful call."""
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", return_value=True
    ):
        assert await get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_verify_ssl_false(hass):
    """Successful call with verify ssl set to false."""
    controller_data = dict(CONTROLLER_DATA)
    controller_data[CONF_VERIFY_SSL] = False
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", return_value=True
    ):
        assert await get_controller(hass, **controller_data)


async def test_get_controller_login_failed(hass):
    """Check that get_controller can handle a failed login."""
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", side_effect=aiounifi.Unauthorized
    ), pytest.raises(AuthenticationRequired):
        await get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_controller_bad_gateway(hass):
    """Check that get_controller can handle controller being unavailable."""
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", side_effect=aiounifi.BadGateway
    ), pytest.raises(CannotConnect):
        await get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_controller_service_unavailable(hass):
    """Check that get_controller can handle controller being unavailable."""
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", side_effect=aiounifi.ServiceUnavailable
    ), pytest.raises(CannotConnect):
        await get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_controller_unavailable(hass):
    """Check that get_controller can handle controller being unavailable."""
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", side_effect=aiounifi.RequestError
    ), pytest.raises(CannotConnect):
        await get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_login_required(hass):
    """Check that get_controller can handle unknown errors."""
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", side_effect=aiounifi.LoginRequired
    ), pytest.raises(AuthenticationRequired):
        await get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_unknown_error(hass):
    """Check that get_controller can handle unknown errors."""
    with patch("aiounifi.Controller.check_unifi_os", return_value=True), patch(
        "aiounifi.Controller.login", side_effect=aiounifi.AiounifiException
    ), pytest.raises(AuthenticationRequired):
        await get_controller(hass, **CONTROLLER_DATA)
