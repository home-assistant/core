"""Tests for the WyBot data update coordinator."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wybot import WybotAuthError
from wybot.dp_models import DP, CleaningStatus
from wybot.models import Group

from homeassistant.components.wybot.const import BLE_MAX_CONSECUTIVE_FAILURES, DOMAIN
from homeassistant.components.wybot.coordinator import (
    BLE_RECOVERY_SECONDS,
    WyBotCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

DEVICE_ID = "dev123"
DOCKER_ID = "dock456"
GROUP_ID = "group1"


def _group_data(with_docker: bool = True) -> dict:
    """Group data."""
    data = {
        "device": {
            "deviceId": DEVICE_ID,
            "deviceName": "Pool Robot",
            "deviceType": "S2 Pro",
            "bleName": "CCBA97932A96",
            "autoUpdate": "1",
            "version": {"Firmware": "1.2.3"},
        },
        "docker": {
            "dockerId": DOCKER_ID,
            "dockerType": "DS20",
            "bleName": "3C8427565A1A",
            "deviceStatus": "online",
            "dockerStatus": "active",
            "schedule": None,
            "version": {"Firmware": "2.0.0"},
        },
        "vision": {
            "visionId": "vis789",
            "privacy": False,
            "log": None,
            "video": None,
            "picture": None,
            "policy": True,
        },
        "name": "My Pool",
        "id": GROUP_ID,
        "autoUpdate": "1",
    }
    if not with_docker:
        data["docker"] = None
    return data


def make_group(with_docker: bool = True) -> Group:
    """Build a Group with a cleaning-status DP populated."""
    group = Group(**_group_data(with_docker=with_docker))
    group.device.dps = {"0": CleaningStatus(DP(id=0, type=4, len=1, data="03"))}
    return group


def make_entry(hass: HomeAssistant, **data) -> MockConfigEntry:
    """Make an account config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="acct", data=data)
    entry.add_to_hass(hass)
    return entry


def make_coordinator(hass: HomeAssistant, **entry_data) -> WyBotCoordinator:
    """Build a real coordinator with all external clients mocked out."""
    entry = make_entry(hass, **entry_data)
    coord = WyBotCoordinator(hass, MagicMock(), entry)

    http = MagicMock()
    http.get_indexed_current_grouped_devices = AsyncMock(return_value={})
    http.register_presence = AsyncMock(return_value=None)
    http.get_devices_and_status = AsyncMock(return_value=None)
    http.authenticate = AsyncMock(return_value=True)
    http.login = AsyncMock(return_value=None)
    http.close = AsyncMock(return_value=None)
    coord.wybot_http_client = http

    ble = MagicMock()
    ble.query_status = AsyncMock(return_value=None)
    ble.send_command = AsyncMock(return_value=(True, None))
    ble.configure_wifi = AsyncMock(return_value=True)
    ble.scan_for_device = AsyncMock(return_value=None)
    coord.wybot_ble_client = ble

    mqtt = MagicMock()
    mqtt.is_connected = MagicMock(return_value=True)
    mqtt.connect = AsyncMock(return_value=True)
    mqtt.disconnect = AsyncMock(return_value=None)
    mqtt.subscribe_for_device = AsyncMock(return_value=None)
    mqtt.ensure_device_sends_statuses = AsyncMock(return_value=None)
    mqtt.send_query_command_for_device = AsyncMock(return_value=True)
    mqtt.send_write_command_for_device = AsyncMock(return_value=True)
    coord.wybot_mqtt_client = mqtt

    return coord


# ---------------------------------------------------------------------------
# construction / simple accessors
# ---------------------------------------------------------------------------


async def test_available_and_vacuums(hass: HomeAssistant) -> None:
    """Test available and vacuums."""
    coord = make_coordinator(hass)
    coord._connection_available = True
    coord.data = {}
    assert coord.available is False  # no data
    coord.data = {GROUP_ID: make_group()}
    assert coord.available is True
    assert coord.vacuums == [GROUP_ID]
    coord._connection_available = False
    assert coord.available is False


async def test_getters(hass: HomeAssistant) -> None:
    """Test getters."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    now = dt_util.utcnow()
    coord._last_ble_poll[DEVICE_ID] = now
    coord._last_mqtt_data[DEVICE_ID] = now
    coord._data_source[DEVICE_ID] = "ble"
    coord._ble_available[DEVICE_ID] = True

    assert coord.get_last_ble_communication(DEVICE_ID) == now
    assert coord.get_last_mqtt_communication(DEVICE_ID) == now
    assert coord.get_data_source(DEVICE_ID) == "ble"
    assert coord.is_ble_available(DEVICE_ID) is True
    assert coord.get_last_ble_communication("unknown") is None

    group = coord.data[GROUP_ID]
    assert coord.get_group(DEVICE_ID) is group
    assert coord.get_group(DOCKER_ID) is group
    assert coord.get_group("nope") is None
    assert coord.get_device_or_docker(DEVICE_ID) is group.device
    assert coord.get_device_or_docker(DOCKER_ID) is group.docker
    assert coord.get_device_or_docker("nope") is None


async def test_get_device_ble_info(hass: HomeAssistant) -> None:
    """Test get device ble info."""
    coord = make_coordinator(hass)
    group = make_group()
    # docker preferred
    assert coord._get_device_ble_info(group) == (group.docker.ble_name, DOCKER_ID)
    # device-only
    group_no_dock = make_group(with_docker=False)
    assert coord._get_device_ble_info(group_no_dock) == (
        group_no_dock.device.ble_name,
        DEVICE_ID,
    )
    # neither BLE name
    group_no_dock.device.ble_name = ""
    assert coord._get_device_ble_info(group_no_dock) == (None, None)


# ---------------------------------------------------------------------------
# _maybe_recover_ble
# ---------------------------------------------------------------------------


async def test_maybe_recover_ble(hass: HomeAssistant) -> None:
    """Test maybe recover ble."""
    coord = make_coordinator(hass)
    coord._ble_command_failures[DEVICE_ID] = 3
    coord._ble_disabled_at[DEVICE_ID] = time.time() - BLE_RECOVERY_SECONDS - 1
    coord._maybe_recover_ble(DEVICE_ID)
    assert DEVICE_ID not in coord._ble_command_failures
    assert DEVICE_ID not in coord._ble_disabled_at


async def test_maybe_recover_ble_not_yet(hass: HomeAssistant) -> None:
    """Test maybe recover ble not yet."""
    coord = make_coordinator(hass)
    coord._ble_command_failures[DEVICE_ID] = 3
    coord._ble_disabled_at[DEVICE_ID] = time.time()
    coord._maybe_recover_ble(DEVICE_ID)
    assert coord._ble_disabled_at[DEVICE_ID]  # still disabled


# ---------------------------------------------------------------------------
# _update_device_dps_from_ble / _update_from_ble_dps
# ---------------------------------------------------------------------------


async def test_update_device_dps_from_ble_docker(hass: HomeAssistant) -> None:
    """Test update device dps from ble docker."""
    coord = make_coordinator(hass)
    group = make_group()
    dps = [{"id": 11, "type": 4, "len": 1, "data": "00"}]
    coord._update_device_dps_from_ble(group, DOCKER_ID, dps)
    assert "11" in group.docker.dps


async def test_update_device_dps_from_ble_device(hass: HomeAssistant) -> None:
    """Test update device dps from ble device."""
    coord = make_coordinator(hass)
    group = make_group(with_docker=False)
    dps = [{"id": 1, "type": 4, "len": 1, "data": "00"}]
    coord._update_device_dps_from_ble(group, DEVICE_ID, dps)
    assert "1" in group.device.dps


async def test_update_device_dps_from_ble_empty(hass: HomeAssistant) -> None:
    """Test update device dps from ble empty."""
    coord = make_coordinator(hass)
    group = make_group()
    before = dict(group.docker.dps)
    coord._update_device_dps_from_ble(group, DOCKER_ID, [])
    assert group.docker.dps == before


async def test_update_from_ble_dps_docker(hass: HomeAssistant) -> None:
    """Test update from ble dps docker."""
    coord = make_coordinator(hass)
    group = make_group()
    coord.data = {GROUP_ID: group}
    coord._update_from_ble_dps(
        group, DOCKER_ID, [{"id": 11, "type": 4, "len": 1, "data": "00"}]
    )
    assert "11" in group.docker.dps
    # BLE responses are recorded as BLE traffic, not MQTT.
    assert DOCKER_ID in coord._last_ble_poll
    assert DOCKER_ID not in coord._last_mqtt_data
    assert coord._data_source[DOCKER_ID] == "ble"


async def test_update_from_ble_dps_device(hass: HomeAssistant) -> None:
    """Test update from ble dps device."""
    coord = make_coordinator(hass)
    group = make_group(with_docker=False)
    coord.data = {GROUP_ID: group}
    coord._update_from_ble_dps(
        group, DEVICE_ID, [{"id": 1, "type": 4, "len": 1, "data": "01"}]
    )
    assert "1" in group.device.dps


async def test_update_from_ble_dps_empty(hass: HomeAssistant) -> None:
    """Test update from ble dps empty."""
    coord = make_coordinator(hass)
    group = make_group()
    coord.data = {GROUP_ID: group}
    # empty returns early, no crash
    coord._update_from_ble_dps(group, DOCKER_ID, [])


async def test_update_from_ble_dps_error(hass: HomeAssistant) -> None:
    """Test update from ble dps error."""
    coord = make_coordinator(hass)
    group = make_group()
    coord.data = {GROUP_ID: group}
    # invalid dp id triggers Command parse failure -> caught, warning logged
    coord._update_from_ble_dps(group, DOCKER_ID, [{"id": "bad"}])


# ---------------------------------------------------------------------------
# BLE polling
# ---------------------------------------------------------------------------


async def test_poll_all_devices_via_ble_success(hass: HomeAssistant) -> None:
    """Test poll all devices via ble success."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_ble_client.query_status.return_value = [
        {"id": 11, "type": 4, "len": 1, "data": "00"}
    ]
    needing = await coord._poll_all_devices_via_ble()
    assert needing == []
    assert coord._ble_available[DOCKER_ID] is True
    assert coord._data_source[DOCKER_ID] == "ble"


async def test_poll_all_devices_via_ble_no_data(hass: HomeAssistant) -> None:
    """Test poll all devices via ble no data."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_ble_client.query_status.return_value = None
    needing = await coord._poll_all_devices_via_ble()
    # Both the robot and the dock are queried over MQTT on fallback.
    assert needing == [DEVICE_ID, DOCKER_ID]
    assert coord._ble_available[DOCKER_ID] is False


async def test_poll_all_devices_via_ble_exception(hass: HomeAssistant) -> None:
    """Test poll all devices via ble exception."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_ble_client.query_status.side_effect = RuntimeError("boom")
    needing = await coord._poll_all_devices_via_ble()
    # Both the robot and the dock are queried over MQTT on fallback.
    assert needing == [DEVICE_ID, DOCKER_ID]
    assert coord._ble_available[DOCKER_ID] is False


async def test_poll_all_devices_via_ble_no_ble_name(hass: HomeAssistant) -> None:
    """Test poll all devices via ble no ble name."""
    coord = make_coordinator(hass)
    group = make_group(with_docker=False)
    group.device.ble_name = ""
    coord.data = {GROUP_ID: group}
    needing = await coord._poll_all_devices_via_ble()
    assert needing == [DEVICE_ID]


# ---------------------------------------------------------------------------
# MQTT polling / connection
# ---------------------------------------------------------------------------


async def test_poll_devices_via_mqtt_empty(hass: HomeAssistant) -> None:
    """Test poll devices via mqtt empty."""
    coord = make_coordinator(hass)
    await coord._poll_devices_via_mqtt([])
    coord.wybot_mqtt_client.ensure_device_sends_statuses.assert_not_called()


async def test_poll_devices_via_mqtt_success(hass: HomeAssistant) -> None:
    """Test poll devices via mqtt success."""
    coord = make_coordinator(hass)
    coord._mqtt_connected = True
    coord.wybot_mqtt_client.is_connected.return_value = True
    await coord._poll_devices_via_mqtt([DEVICE_ID])
    coord.wybot_mqtt_client.ensure_device_sends_statuses.assert_called_with(DEVICE_ID)


async def test_poll_devices_via_mqtt_connect_fails(hass: HomeAssistant) -> None:
    """Test poll devices via mqtt connect fails."""
    coord = make_coordinator(hass)
    coord.wybot_mqtt_client.connect.side_effect = RuntimeError("no broker")
    await coord._poll_devices_via_mqtt([DEVICE_ID])
    coord.wybot_mqtt_client.ensure_device_sends_statuses.assert_not_called()


async def test_ensure_mqtt_connected_already(hass: HomeAssistant) -> None:
    """Test ensure mqtt connected already."""
    coord = make_coordinator(hass)
    coord._mqtt_connected = True
    coord.wybot_mqtt_client.is_connected.return_value = True
    assert await coord._ensure_mqtt_connected() is True


async def test_ensure_mqtt_connected_drift(hass: HomeAssistant) -> None:
    """Test ensure mqtt connected drift."""
    coord = make_coordinator(hass)
    coord._mqtt_connected = True
    coord.data = {GROUP_ID: make_group()}
    # paho says disconnected first, then connect succeeds
    coord.wybot_mqtt_client.is_connected.return_value = False
    assert await coord._ensure_mqtt_connected() is True
    coord.wybot_mqtt_client.connect.assert_called()
    # subscribed for device + docker
    assert coord.wybot_mqtt_client.subscribe_for_device.call_count >= 2


async def test_ensure_mqtt_connected_fails(hass: HomeAssistant) -> None:
    """Test ensure mqtt connected fails."""
    coord = make_coordinator(hass)
    coord.wybot_mqtt_client.connect.side_effect = RuntimeError("fail")
    assert await coord._ensure_mqtt_connected() is False
    assert coord._mqtt_connected is False


async def test_ensure_mqtt_connected_not_ready(hass: HomeAssistant) -> None:
    """connect() reporting it never came up leaves us disconnected."""
    coord = make_coordinator(hass)
    coord.wybot_mqtt_client.connect = AsyncMock(return_value=False)
    assert await coord._ensure_mqtt_connected() is False
    assert coord._mqtt_connected is False


# ---------------------------------------------------------------------------
# subscribe_mqtt / query_all_device_status / send_write_command
# ---------------------------------------------------------------------------


async def test_subscribe_mqtt(hass: HomeAssistant) -> None:
    """Test subscribe mqtt."""
    coord = make_coordinator(hass)
    data = {GROUP_ID: make_group(), "g2": make_group(with_docker=False)}
    data["g2"].device.dps = {}
    await coord.subscribe_mqtt(data)
    # 2 devices + 1 docker
    assert coord.wybot_mqtt_client.subscribe_for_device.call_count == 3


async def test_query_all_device_status(hass: HomeAssistant) -> None:
    """Test query all device status."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_mqtt_client.is_connected.return_value = True
    await coord.query_all_device_status()
    assert coord.wybot_mqtt_client.ensure_device_sends_statuses.call_count == 2


async def test_query_all_device_status_disconnected(hass: HomeAssistant) -> None:
    """Test query all device status disconnected."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_mqtt_client.is_connected.return_value = False
    await coord.query_all_device_status()
    coord.wybot_mqtt_client.ensure_device_sends_statuses.assert_not_called()


async def test_send_write_command(hass: HomeAssistant) -> None:
    """Test send write command."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    await coord.send_write_command(group, dp)
    # once for device, once for docker
    assert coord.wybot_mqtt_client.send_write_command_for_device.call_count == 2


# ---------------------------------------------------------------------------
# async_send_command
# ---------------------------------------------------------------------------


async def test_async_send_command_ble_success(hass: HomeAssistant) -> None:
    """Test async send command ble success."""
    coord = make_coordinator(hass)
    group = make_group()
    coord.data = {GROUP_ID: group}
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (
        True,
        [{"id": 0, "type": 4, "len": 1, "data": "01"}],
    )
    assert await coord.async_send_command(group, dp) is True
    assert coord._ble_command_failures[DEVICE_ID] == 0
    coord.wybot_mqtt_client.send_write_command_for_device.assert_not_called()


async def test_async_send_command_ble_device_name(hass: HomeAssistant) -> None:
    # No docker -> uses the device ble_name branch
    """Test async send command ble device name."""
    coord = make_coordinator(hass)
    group = make_group(with_docker=False)
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (True, None)
    assert await coord.async_send_command(group, dp) is True
    coord.wybot_ble_client.send_command.assert_awaited_once()


async def test_async_send_command_ble_success_no_dps(hass: HomeAssistant) -> None:
    """Test async send command ble success no dps."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (True, None)
    assert await coord.async_send_command(group, dp) is True


async def test_async_send_command_ble_failure_falls_back(hass: HomeAssistant) -> None:
    """Test async send command ble failure falls back."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (False, None)
    assert await coord.async_send_command(group, dp) is True
    assert coord._ble_command_failures[DEVICE_ID] == 1
    assert coord.wybot_mqtt_client.send_write_command_for_device.called


async def test_async_send_command_ble_disables_after_max(hass: HomeAssistant) -> None:
    """Test async send command ble disables after max."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (False, None)
    coord._ble_command_failures[DEVICE_ID] = BLE_MAX_CONSECUTIVE_FAILURES - 1
    assert await coord.async_send_command(group, dp) is True
    assert coord._ble_command_failures[DEVICE_ID] == BLE_MAX_CONSECUTIVE_FAILURES
    assert DEVICE_ID in coord._ble_disabled_at


async def test_async_send_command_ble_exception(hass: HomeAssistant) -> None:
    """Test async send command ble exception."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.side_effect = RuntimeError("ble err")
    assert await coord.async_send_command(group, dp) is True
    assert coord._ble_command_failures[DEVICE_ID] == 1


async def test_async_send_command_ble_exception_disables(hass: HomeAssistant) -> None:
    """Test async send command ble exception disables."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.side_effect = RuntimeError("ble err")
    coord._ble_command_failures[DEVICE_ID] = BLE_MAX_CONSECUTIVE_FAILURES - 1
    assert await coord.async_send_command(group, dp) is True
    assert DEVICE_ID in coord._ble_disabled_at


async def test_async_send_command_no_ble_name(hass: HomeAssistant) -> None:
    """Test async send command no ble name."""
    coord = make_coordinator(hass)
    group = make_group(with_docker=False)
    group.device.ble_name = ""
    dp = group.device.dps["0"]
    assert await coord.async_send_command(group, dp) is True
    coord.wybot_ble_client.send_command.assert_not_called()
    assert coord.wybot_mqtt_client.send_write_command_for_device.called


async def test_async_send_command_ble_globally_disabled(hass: HomeAssistant) -> None:
    """Test async send command ble globally disabled."""
    coord = make_coordinator(hass)
    coord._ble_command_enabled = False
    group = make_group()
    dp = group.device.dps["0"]
    assert await coord.async_send_command(group, dp) is True
    coord.wybot_ble_client.send_command.assert_not_called()


async def test_async_send_command_ble_too_many_failures(hass: HomeAssistant) -> None:
    """Test async send command ble too many failures."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord._ble_command_failures[DEVICE_ID] = BLE_MAX_CONSECUTIVE_FAILURES
    assert await coord.async_send_command(group, dp) is True
    coord.wybot_ble_client.send_command.assert_not_called()


async def test_async_send_command_mqtt_fallback_ensures_connection(
    hass: HomeAssistant,
) -> None:
    """The MQTT fallback connects the client before publishing the command."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (False, None)
    coord._mqtt_connected = False
    assert await coord.async_send_command(group, dp) is True
    coord.wybot_mqtt_client.connect.assert_awaited()
    assert coord.wybot_mqtt_client.send_write_command_for_device.called


async def test_async_send_command_mqtt_unavailable_returns_false(
    hass: HomeAssistant,
) -> None:
    """When BLE fails and MQTT cannot connect, the command is not sent."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (False, None)
    coord._mqtt_connected = False
    coord.wybot_mqtt_client.is_connected = MagicMock(return_value=False)
    coord.wybot_mqtt_client.connect = AsyncMock(side_effect=RuntimeError("no mqtt"))
    assert await coord.async_send_command(group, dp) is False
    coord.wybot_mqtt_client.send_write_command_for_device.assert_not_called()


async def test_async_send_command_mqtt_publish_dropped_returns_false(
    hass: HomeAssistant,
) -> None:
    """A dropped MQTT publish is reported as failure, not silent success."""
    coord = make_coordinator(hass)
    group = make_group()
    dp = group.device.dps["0"]
    coord.wybot_ble_client.send_command.return_value = (False, None)
    coord._mqtt_connected = True
    # Connected, but the broker dropped the publish (disconnected mid-send).
    coord.wybot_mqtt_client.send_write_command_for_device = AsyncMock(
        return_value=False
    )
    assert await coord.async_send_command(group, dp) is False


async def test_reset_ble_command_failures(hass: HomeAssistant) -> None:
    """Test reset ble command failures."""
    coord = make_coordinator(hass)
    coord._ble_command_failures = {DEVICE_ID: 2, "other": 1}
    coord.reset_ble_command_failures(DEVICE_ID)
    assert DEVICE_ID not in coord._ble_command_failures
    coord.reset_ble_command_failures()
    assert coord._ble_command_failures == {}


# ---------------------------------------------------------------------------
# async_stop
# ---------------------------------------------------------------------------


async def test_async_stop_connected(hass: HomeAssistant) -> None:
    """Test async stop connected."""
    coord = make_coordinator(hass)
    coord._mqtt_connected = True
    await coord.async_stop()
    coord.wybot_mqtt_client.disconnect.assert_called_once()
    assert coord._mqtt_connected is False


async def test_async_stop_not_connected(hass: HomeAssistant) -> None:
    """Disconnect is called even when the flag is unset to reap a leaked task."""
    coord = make_coordinator(hass)
    coord._mqtt_connected = False
    await coord.async_stop()
    coord.wybot_mqtt_client.disconnect.assert_called_once()
    assert coord._mqtt_connected is False


# ---------------------------------------------------------------------------
# on_message
# ---------------------------------------------------------------------------


def _cmd(dp_id: int = 0, data: str = "03") -> dict:
    """Cmd."""
    return {"cmd": 5, "ts": 0, "dp": [{"id": dp_id, "type": 4, "len": 1, "data": data}]}


async def test_on_message_will_online(hass: HomeAssistant) -> None:
    """Test on message will online."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.on_message(f"/will/{DEVICE_ID}", {"online": "1"})
    assert DEVICE_ID in coord._online_devices
    assert coord.data[GROUP_ID].device.online is True
    coord.wybot_mqtt_client.ensure_device_sends_statuses.assert_called_with(DEVICE_ID)
    await hass.async_block_till_done()


async def test_on_message_non_mapping_payload_ignored(hass: HomeAssistant) -> None:
    """A non-mapping (e.g. raw bytes) MQTT payload is ignored, not crashing."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.on_message(f"/will/{DEVICE_ID}", b"not-json")
    assert DEVICE_ID not in coord._online_devices


async def test_on_message_malformed_query_payload_ignored(
    hass: HomeAssistant,
) -> None:
    """A malformed query-response payload does not escape the callback."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    # Missing required Command fields -> model validation error, handled.
    coord.on_message(
        f"/device/DATA/recv_transparent_query_data/{DEVICE_ID}", {"bad": "payload"}
    )
    await hass.async_block_till_done()


async def test_on_message_malformed_cmd_payload_ignored(hass: HomeAssistant) -> None:
    """A malformed command-response payload does not escape the callback."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.on_message(
        f"/device/DATA/recv_transparent_cmd_data/{DEVICE_ID}", {"bad": "payload"}
    )
    await hass.async_block_till_done()


async def test_on_message_will_offline_docker(hass: HomeAssistant) -> None:
    """Test on message will offline docker."""
    coord = make_coordinator(hass)
    group = make_group()
    coord.data = {GROUP_ID: group}
    coord._online_devices.add(DOCKER_ID)
    coord.on_message(f"/will/{DOCKER_ID}", {"online": "0"})
    assert DOCKER_ID not in coord._online_devices
    assert coord.data[GROUP_ID].docker.online is False
    await hass.async_block_till_done()


async def test_on_message_will_unknown_device(hass: HomeAssistant) -> None:
    """Test on message will unknown device."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    # unknown device id -> group is None, but data_updated still True
    coord.on_message("/will/unknown", {"online": "1"})
    await hass.async_block_till_done()


async def test_on_message_send_transparent_data_docker(hass: HomeAssistant) -> None:
    """Test on message send transparent data docker."""
    coord = make_coordinator(hass)
    group = make_group()
    coord.data = {GROUP_ID: group}
    coord.on_message(f"/device/DATA/send_transparent_data/{DOCKER_ID}", _cmd(11, "00"))
    assert "11" in coord.data[GROUP_ID].docker.dps
    await hass.async_block_till_done()


async def test_on_message_send_transparent_data_device(hass: HomeAssistant) -> None:
    """Test on message send transparent data device."""
    coord = make_coordinator(hass)
    group = make_group(with_docker=False)
    coord.data = {GROUP_ID: group}
    coord.on_message(f"/device/DATA/send_transparent_data/{DEVICE_ID}", _cmd(1, "01"))
    assert "1" in coord.data[GROUP_ID].device.dps
    await hass.async_block_till_done()


async def test_on_message_send_transparent_data_bad(hass: HomeAssistant) -> None:
    """Test on message send transparent data bad."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    # invalid Command payload -> parse fails -> returns early
    coord.on_message(
        f"/device/DATA/send_transparent_data/{DOCKER_ID}", {"garbage": True}
    )
    await hass.async_block_till_done()


async def test_on_message_recv_query_data(hass: HomeAssistant) -> None:
    """Test on message recv query data."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.on_message(f"/device/DATA/recv_transparent_query_data/{DOCKER_ID}", _cmd())
    await hass.async_block_till_done()


async def test_on_message_recv_cmd_data_docker(hass: HomeAssistant) -> None:
    """Test on message recv cmd data docker."""
    coord = make_coordinator(hass)
    group = make_group()
    coord.data = {GROUP_ID: group}
    coord.on_message(
        f"/device/DATA/recv_transparent_cmd_data/{DOCKER_ID}", _cmd(11, "01")
    )
    assert "11" in coord.data[GROUP_ID].docker.dps
    await hass.async_block_till_done()


async def test_on_message_recv_cmd_data_device(hass: HomeAssistant) -> None:
    """Test on message recv cmd data device."""
    coord = make_coordinator(hass)
    group = make_group(with_docker=False)
    coord.data = {GROUP_ID: group}
    coord.on_message(
        f"/device/DATA/recv_transparent_cmd_data/{DEVICE_ID}", _cmd(1, "01")
    )
    assert "1" in coord.data[GROUP_ID].device.dps
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# http_refresh_data
# ---------------------------------------------------------------------------


async def test_http_refresh_data_success(hass: HomeAssistant) -> None:
    """Test http refresh data success."""
    coord = make_coordinator(hass)
    data = {GROUP_ID: make_group()}
    coord.wybot_http_client.get_indexed_current_grouped_devices.return_value = data
    await coord.http_refresh_data()
    assert coord.data is data
    assert coord._http_failure_count == 0


async def test_http_refresh_data_empty_retries(hass: HomeAssistant) -> None:
    """Test http refresh data empty retries."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.get_indexed_current_grouped_devices.return_value = {}
    with (
        patch(
            "homeassistant.components.wybot.coordinator.asyncio.sleep",
            AsyncMock(),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coord.http_refresh_data()


async def test_http_refresh_data_auth_error(hass: HomeAssistant) -> None:
    """Test http refresh data auth error."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.get_indexed_current_grouped_devices.side_effect = (
        WybotAuthError("bad")
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coord.http_refresh_data()


async def test_http_refresh_data_single_failure_updates_failed(
    hass: HomeAssistant,
) -> None:
    """One failure raises UpdateFailed (pywybot already retried internally)."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.get_indexed_current_grouped_devices.side_effect = (
        RuntimeError("net down")
    )
    with pytest.raises(UpdateFailed):
        await coord.http_refresh_data()
    assert coord._http_failure_count == 1
    assert coord._connection_available is False


async def test_http_refresh_data_connection_failures(hass: HomeAssistant) -> None:
    """Repeated failures escalate to ConfigEntryNotReady."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.get_indexed_current_grouped_devices.side_effect = (
        RuntimeError("net down")
    )
    coord._http_failure_count = 2  # third consecutive failure marks not-ready
    with pytest.raises(ConfigEntryNotReady):
        await coord.http_refresh_data()
    assert coord._http_failure_count >= 3


# ---------------------------------------------------------------------------
# _async_update_data
# ---------------------------------------------------------------------------


async def test_async_update_data_initial_load(hass: HomeAssistant) -> None:
    """Test async update data initial load."""
    coord = make_coordinator(hass)
    data = {GROUP_ID: make_group()}
    coord.wybot_http_client.get_indexed_current_grouped_devices.return_value = data
    coord.wybot_ble_client.query_status.return_value = [
        {"id": 11, "type": 4, "len": 1, "data": "00"}
    ]
    result = await coord._async_update_data()
    assert result is data
    assert coord.initial_load is True
    assert coord._connection_available is True


async def test_async_update_data_subsequent(hass: HomeAssistant) -> None:
    """Test async update data subsequent."""
    coord = make_coordinator(hass)
    coord.initial_load = True
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_ble_client.query_status.return_value = [
        {"id": 11, "type": 4, "len": 1, "data": "00"}
    ]
    result = await coord._async_update_data()
    assert result == coord.data


async def test_async_update_data_no_data(hass: HomeAssistant) -> None:
    """Test async update data no data."""
    coord = make_coordinator(hass)
    coord.initial_load = True
    coord.data = {}
    with pytest.raises(UpdateFailed) as err:
        await coord._async_update_data()
    # The specific no_data reason must survive, not be masked as update_failed.
    assert err.value.translation_key == "no_data"
    assert coord._connection_available is False


async def test_async_update_data_full_outage_marks_unavailable(
    hass: HomeAssistant,
) -> None:
    """A total transport outage marks unavailable rather than serving stale data."""
    coord = make_coordinator(hass)
    coord.initial_load = True
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_ble_client.query_status.return_value = None
    coord.wybot_mqtt_client.is_connected = MagicMock(return_value=False)
    coord.wybot_mqtt_client.connect = AsyncMock(side_effect=RuntimeError("no mqtt"))
    coord.wybot_http_client.get_indexed_current_grouped_devices = AsyncMock(
        side_effect=RuntimeError("no http")
    )
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    assert coord._connection_available is False


async def test_async_update_data_available_via_recent_http(
    hass: HomeAssistant,
) -> None:
    """Recent HTTP contact keeps the integration available without BLE/MQTT."""
    coord = make_coordinator(hass)
    coord.initial_load = True
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_ble_client.query_status.return_value = None
    coord.wybot_mqtt_client.is_connected = MagicMock(return_value=False)
    coord.wybot_mqtt_client.connect = AsyncMock(side_effect=RuntimeError("no mqtt"))
    # The HTTP keepalive still succeeds (default mock), so the account is reached.
    result = await coord._async_update_data()
    assert result == coord.data
    assert coord._connection_available is True


async def test_recently_reached_false_when_all_stale(hass: HomeAssistant) -> None:
    """No transport timestamps at all means the integration is not reachable."""
    coord = make_coordinator(hass)
    assert coord._recently_reached() is False


async def test_async_update_data_auth_error(hass: HomeAssistant) -> None:
    """Test async update data auth error."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.register_presence.side_effect = WybotAuthError("bad")
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_async_update_data_config_entry_auth_failed_passthrough(
    hass: HomeAssistant,
) -> None:
    """Test async update data config entry auth failed passthrough."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.get_indexed_current_grouped_devices.side_effect = (
        WybotAuthError("bad")
    )
    # http_refresh_data converts to ConfigEntryAuthFailed, which passes through
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_async_update_data_config_entry_not_ready_passthrough(
    hass: HomeAssistant,
) -> None:
    """Test async update data config entry not ready passthrough."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.get_indexed_current_grouped_devices.side_effect = (
        RuntimeError("net")
    )
    coord._http_failure_count = 2  # next failure escalates to ConfigEntryNotReady
    with pytest.raises(ConfigEntryNotReady):
        await coord._async_update_data()


async def test_async_update_data_timeout(hass: HomeAssistant) -> None:
    """Test async update data timeout."""
    coord = make_coordinator(hass)
    coord.initial_load = True
    coord.data = {GROUP_ID: make_group()}
    with (
        patch.object(
            coord, "_poll_all_devices_via_ble", side_effect=TimeoutError("slow")
        ),
        pytest.raises(UpdateFailed),
    ):
        await coord._async_update_data()


async def test_async_update_data_generic_error(hass: HomeAssistant) -> None:
    """Test async update data generic error."""
    coord = make_coordinator(hass)
    coord.initial_load = True
    coord.data = {GROUP_ID: make_group()}
    with (
        patch.object(
            coord, "_poll_all_devices_via_ble", side_effect=ValueError("oops")
        ),
        pytest.raises(UpdateFailed),
    ):
        await coord._async_update_data()


async def test_async_update_data_mqtt_fallback(hass: HomeAssistant) -> None:
    """Test async update data mqtt fallback."""
    coord = make_coordinator(hass)
    coord.initial_load = True
    coord.data = {GROUP_ID: make_group()}
    # BLE returns nothing -> device needs MQTT
    coord.wybot_ble_client.query_status.return_value = None
    coord._mqtt_connected = True
    coord.wybot_mqtt_client.is_connected.return_value = True
    result = await coord._async_update_data()
    assert result == coord.data
    coord.wybot_mqtt_client.ensure_device_sends_statuses.assert_called()


# ---------------------------------------------------------------------------
# _maybe_refresh_http_session
# ---------------------------------------------------------------------------


async def test_maybe_refresh_http_session_throttled(hass: HomeAssistant) -> None:
    """Test maybe refresh http session throttled."""
    coord = make_coordinator(hass)
    coord._last_http_refresh_time = time.time()
    await coord._maybe_refresh_http_session()
    coord.wybot_http_client.register_presence.assert_not_called()


async def test_maybe_refresh_http_session_runs(hass: HomeAssistant) -> None:
    """Test maybe refresh http session runs."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord._mqtt_connected = True
    coord.wybot_mqtt_client.is_connected.return_value = True
    await coord._maybe_refresh_http_session()
    coord.wybot_http_client.register_presence.assert_called()
    coord.wybot_http_client.get_indexed_current_grouped_devices.assert_called()


async def test_merge_http_groups_discovers_and_gap_fills(
    hass: HomeAssistant,
) -> None:
    """New groups are added; cloud DPs only fill gaps on known groups."""
    coord = make_coordinator(hass)
    existing = make_group()
    existing.device.dps = {"0": "local"}  # a fresher BLE/MQTT value
    coord.data = {GROUP_ID: existing}

    incoming = make_group()
    incoming.device.dps = {"0": "cloud", "99": "cloud-only"}
    new_group = make_group(with_docker=False)
    coord._merge_http_groups({GROUP_ID: incoming, "g2": new_group})

    # Newly discovered device is added.
    assert "g2" in coord.data
    # Local value is preserved; cloud only fills the missing key.
    assert coord.data[GROUP_ID].device.dps["0"] == "local"
    assert coord.data[GROUP_ID].device.dps["99"] == "cloud-only"


async def test_maybe_refresh_http_session_discovers_new_device(
    hass: HomeAssistant,
) -> None:
    """The periodic HTTP refresh applies its response so new devices appear."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    coord.wybot_mqtt_client.is_connected.return_value = True
    coord.wybot_http_client.get_indexed_current_grouped_devices = AsyncMock(
        return_value={"g2": make_group(with_docker=False)}
    )
    await coord._maybe_refresh_http_session()
    assert "g2" in coord.data


async def test_maybe_refresh_http_session_auth_error(hass: HomeAssistant) -> None:
    """Test maybe refresh http session auth error."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.register_presence.side_effect = WybotAuthError("bad")
    with pytest.raises(WybotAuthError):
        await coord._maybe_refresh_http_session()


async def test_maybe_refresh_http_session_non_critical_error(
    hass: HomeAssistant,
) -> None:
    """Test maybe refresh http session non critical error."""
    coord = make_coordinator(hass)
    coord.wybot_http_client.register_presence.side_effect = RuntimeError("meh")
    # swallowed, no raise
    await coord._maybe_refresh_http_session()


async def test_maybe_refresh_http_session_mqtt_keepalive_error(
    hass: HomeAssistant,
) -> None:
    """Test maybe refresh http session mqtt keepalive error."""
    coord = make_coordinator(hass)
    coord.data = {GROUP_ID: make_group()}
    # _ensure_mqtt_connected raising is swallowed by the keepalive try/except
    with patch.object(
        coord, "_ensure_mqtt_connected", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        await coord._maybe_refresh_http_session()
