"""Tests of UniFi Network entries connecting with only an Integration API key."""

from collections.abc import Callable
from datetime import timedelta
import json
from typing import Any
from unittest.mock import patch

import aiohttp
import aiounifi
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from yarl import URL

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_CLIENT_SOURCE,
    CONF_DETECTION_TIME,
    CONF_MORE_OPTIONS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DOMAIN,
)
from homeassistant.components.unifi.hub.connection import LOGIN_REJECTIONS_BEFORE_REAUTH
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    DEFAULT_SITE,
    MAX_RETRY_DELAY,
    NETWORK_SITE_ID,
    NETWORK_URL,
    ConfigEntryFactoryType,
    network_page,
)

SITE_URL = f"{NETWORK_URL}/sites/{NETWORK_SITE_ID}"

SWITCH_ID = "4ff3bc5f-6d39-3d2e-9bfd-0f2bf6c3f1d4"
SWITCH_MAC = "00:00:00:00:01:01"
SWITCH = {
    "features": ["switching"],
    "firmwareUpdatable": False,
    "firmwareVersion": "7.1.26",
    "id": SWITCH_ID,
    "interfaces": ["ports"],
    "ipAddress": "10.0.1.2",
    "macAddress": SWITCH_MAC,
    "model": "USW Pro 24 PoE",
    "name": "Switch",
    "state": "ONLINE",
    "supported": True,
}
SWITCH_DETAILS = {
    **SWITCH,
    "interfaces": {
        "ports": [
            {
                "connector": "RJ45",
                "idx": 1,
                "maxSpeedMbps": 1000,
                "poe": {
                    "enabled": True,
                    "standard": "802.3at",
                    "state": "UP",
                    "type": 2,
                },
                "speedMbps": 1000,
                "state": "UP",
            },
            {
                "connector": "SFP",
                "idx": 25,
                "maxSpeedMbps": 10000,
                "state": "DOWN",
            },
        ]
    },
}
SWITCH_STATISTICS = {
    "cpuUtilizationPct": 12.5,
    "lastHeartbeatAt": "2026-11-07T10:00:00Z",
    "loadAverage1Min": 0.25,
    "memoryUtilizationPct": 40.1,
    "uptimeSec": 3600,
}

WIRELESS_CLIENT_MAC = "00:00:00:00:00:01"
WIRELESS_CLIENT = {
    "access": {"type": "DEFAULT"},
    "connectedAt": "2026-11-07T09:00:00Z",
    "id": "a2d6c6a8-0f6c-36b7-9e4c-5f5a1c0d9f01",
    "ipAddress": "10.0.0.10",
    "macAddress": WIRELESS_CLIENT_MAC,
    "name": "Phone",
    "type": "WIRELESS",
    "uplinkDeviceId": SWITCH_ID,
}
WIRED_CLIENT_MAC = "00:00:00:00:00:02"
WIRED_CLIENT = {
    "access": {"type": "DEFAULT"},
    "id": "b2d6c6a8-0f6c-36b7-9e4c-5f5a1c0d9f02",
    "ipAddress": "10.0.0.11",
    "macAddress": WIRED_CLIENT_MAC,
    "name": "Desktop",
    "type": "WIRED",
    "uplinkDeviceId": SWITCH_ID,
}

WIRELESS_TRACKER = "device_tracker.phone"
SWITCH_TRACKER = "device_tracker.switch"
RESTART_BUTTON = "button.switch_restart"
POWER_CYCLE_BUTTON = "button.switch_port_1_power_cycle"


@pytest.fixture(autouse=True)
def fixture_network_payloads(
    network_client_payload: list[dict[str, Any]],
    network_device_payload: list[dict[str, Any]],
    network_device_details_payload: dict[str, dict[str, Any]],
    network_device_statistics_payload: dict[str, dict[str, Any]],
) -> None:
    """Populate a site with a switch and two clients."""
    network_client_payload.extend([WIRELESS_CLIENT, WIRED_CLIENT])
    network_device_payload.append(SWITCH)
    network_device_details_payload[SWITCH_ID] = SWITCH_DETAILS
    network_device_statistics_payload[SWITCH_ID] = SWITCH_STATISTICS


def mock_clients(
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
    clients: list[dict[str, Any]],
) -> None:
    """Answer the next client list with other clients."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE_URL}/clients", json=network_page(clients))
    mock_network_requests()


@pytest.mark.parametrize(
    "platform", [Platform.BUTTON, Platform.DEVICE_TRACKER, Platform.SENSOR]
)
@pytest.mark.freeze_time("2026-11-07 10:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    network_config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Validate the entities an API key provides."""
    with patch("homeassistant.components.unifi.API_KEY_ONLY_PLATFORMS", [platform]):
        config_entry = await network_config_entry_factory()

    assert config_entry.state is ConfigEntryState.LOADED
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("network_config_entry_setup")
async def test_only_api_key_platforms(hass: HomeAssistant) -> None:
    """Platforms the Integration API cannot fill are not set up."""
    assert {
        platform
        for platform in Platform
        if f"{DOMAIN}.{platform}" in hass.config.components
    } == {Platform.BUTTON, Platform.DEVICE_TRACKER, Platform.SENSOR}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_tracker_follows_polls(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
    network_config_entry_factory: ConfigEntryFactoryType,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A client is away once it is not listed for the detection time."""
    await network_config_entry_factory()
    assert hass.states.get(WIRELESS_TRACKER).state == STATE_HOME
    assert hass.states.get(WIRELESS_TRACKER).attributes["ip"] == "10.0.0.10"

    mock_clients(aioclient_mock, mock_network_requests, [WIRED_CLIENT])
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # Still within the detection time
    assert hass.states.get(WIRELESS_TRACKER).state == STATE_HOME

    freezer.tick(timedelta(seconds=300))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(WIRELESS_TRACKER).state == STATE_NOT_HOME


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {CONF_TRACK_WIRED_CLIENTS: False},
        {CONF_TRACK_CLIENTS: False, CONF_TRACK_DEVICES: False},
        {CONF_TRACK_CLIENTS: False, CONF_CLIENT_SOURCE: [WIRED_CLIENT_MAC]},
    ],
    ids=["no_wired_clients", "no_clients_or_devices", "client_source_ignored"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tracker_options(
    hass: HomeAssistant,
    network_config_entry_factory: ConfigEntryFactoryType,
    config_entry_options: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Options limit which clients and devices are tracked."""
    await network_config_entry_factory()

    assert sorted(hass.states.async_entity_ids(TRACKER_DOMAIN)) == snapshot


async def test_restores_disconnected_client(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    network_config_entry: MockConfigEntry,
    network_config_entry_factory: ConfigEntryFactoryType,
    network_client_payload: list[dict[str, Any]],
) -> None:
    """A tracked client that is not connected keeps its tracker."""
    network_client_payload.remove(WIRELESS_CLIENT)
    for mac, name in ((WIRELESS_CLIENT_MAC, "phone"), (WIRED_CLIENT_MAC, "desktop")):
        entity_registry.async_get_or_create(
            Platform.DEVICE_TRACKER,
            DOMAIN,
            f"{DEFAULT_SITE}-{mac}",
            suggested_object_id=name,
            config_entry=network_config_entry,
        )

    await network_config_entry_factory()

    assert hass.states.get(WIRELESS_TRACKER).state == STATE_NOT_HOME
    assert hass.states.get("device_tracker.desktop").state == STATE_HOME


async def test_prunes_disabled_tracker_of_unlisted_client(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    network_config_entry: MockConfigEntry,
    network_config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """A disabled tracker of a client that is not connected is removed."""
    mac = "00:00:00:00:00:03"
    device = device_registry.async_get_or_create(
        config_entry_id=network_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
    )
    entry = entity_registry.async_get_or_create(
        Platform.DEVICE_TRACKER,
        DOMAIN,
        f"{DEFAULT_SITE}-{mac}",
        config_entry=network_config_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    await network_config_entry_factory()

    assert entity_registry.async_get(entry.entity_id) is None
    assert device_registry.async_get(device.id) is None


@pytest.mark.parametrize(
    ("entity_id", "path", "data"),
    [
        (RESTART_BUTTON, f"devices/{SWITCH_ID}/actions", {"action": "RESTART"}),
        (
            POWER_CYCLE_BUTTON,
            f"devices/{SWITCH_ID}/interfaces/ports/1/actions",
            {"action": "POWER_CYCLE"},
        ),
    ],
)
@pytest.mark.usefixtures("network_config_entry_setup")
async def test_buttons(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_id: str,
    path: str,
    data: dict[str, str],
) -> None:
    """Buttons send their action to the Integration API."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{SITE_URL}/{path}", json={})

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert aioclient_mock.call_count == 1
    assert json.loads(aioclient_mock.mock_calls[0][2]) == data


@pytest.mark.usefixtures("network_config_entry_setup")
async def test_offline_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
) -> None:
    """Device controls and statistics are unavailable while it is offline."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{SITE_URL}/devices", json=network_page([{**SWITCH, "state": "OFFLINE"}])
    )
    mock_network_requests()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.switch_state").state == "offline"
    assert hass.states.get(RESTART_BUTTON).state == STATE_UNAVAILABLE
    assert hass.states.get(POWER_CYCLE_BUTTON).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.switch_cpu_utilization").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("network_config_entry_setup")
async def test_poll_failure_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
) -> None:
    """A failing console makes entities unavailable until it answers again."""
    aioclient_mock.clear_requests()
    for path in ("info", f"sites/{NETWORK_SITE_ID}/devices"):
        aioclient_mock.get(f"{NETWORK_URL}/{path}", status=503)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.switch_state").state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    mock_network_requests()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.switch_state").state == "online"


@pytest.mark.parametrize(
    ("status", "state", "reauth"),
    [
        (401, ConfigEntryState.SETUP_ERROR, True),
        (404, ConfigEntryState.SETUP_RETRY, False),
        (503, ConfigEntryState.SETUP_RETRY, False),
    ],
    ids=["rejected_key", "no_integration_api", "unavailable"],
)
async def test_setup_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_config_entry: MockConfigEntry,
    status: int,
    state: ConfigEntryState,
    reauth: bool,
) -> None:
    """Setup fails depending on how the console answers the key."""
    aioclient_mock.get(f"{NETWORK_URL}/info", status=status)

    await hass.config_entries.async_setup(network_config_entry.entry_id)
    await hass.async_block_till_done()

    assert network_config_entry.state is state
    assert (
        any(network_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        is reauth
    )


@pytest.mark.parametrize("network_site_payload", [[]])
async def test_site_not_found(
    hass: HomeAssistant,
    network_config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """A console that lists no site is not ready yet."""
    config_entry = await network_config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "network_site_payload",
    [[{"id": "other-site", "internalReference": "other", "name": "Other"}]],
)
async def test_site_removed(
    hass: HomeAssistant,
    network_config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """A site that no longer exists stops setup."""
    config_entry = await network_config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_site_unique_id_moves_to_uuid(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    network_config_entry: MockConfigEntry,
    network_config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """An entry keyed by the ObjectId of a site is keyed by its UUID instead."""
    object_id = "5ba29dd4e3c58f026e9d7c38"
    hass.config_entries.async_update_entry(network_config_entry, unique_id=object_id)
    device_registry.async_get_or_create(
        config_entry_id=network_config_entry.entry_id,
        identifiers={(DOMAIN, object_id)},
    )

    await network_config_entry_factory()

    assert network_config_entry.state is ConfigEntryState.LOADED
    assert network_config_entry.unique_id == NETWORK_SITE_ID
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, NETWORK_SITE_ID), network_config_entry.entry_id
    )


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    network_config_entry_setup: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Diagnostics redact the key and MAC addresses."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, network_config_entry_setup
    ) == snapshot(exclude=props("created_at", "modified_at"))


async def test_options_flow(
    hass: HomeAssistant, network_config_entry_setup: MockConfigEntry
) -> None:
    """Only options the Integration API supports are offered."""
    result = await hass.config_entries.options.async_init(
        network_config_entry_setup.entry_id
    )

    assert list(result["data_schema"].schema) == [
        CONF_TRACK_CLIENTS,
        CONF_TRACK_DEVICES,
        CONF_MORE_OPTIONS,
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: True,
            CONF_MORE_OPTIONS: {
                CONF_TRACK_WIRED_CLIENTS: False,
                CONF_DETECTION_TIME: 60,
            },
        },
    )

    assert network_config_entry_setup.options[CONF_TRACK_CLIENTS] is False
    assert network_config_entry_setup.options[CONF_DETECTION_TIME] == 60


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    network_config_entry_setup: MockConfigEntry,
) -> None:
    """A listed device cannot be removed, a client can."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)

    async def remove(mac: str) -> bool:
        device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), network_config_entry_setup.entry_id
        )
        assert device is not None
        response = await client.remove_device(device.id)
        return response["success"]

    assert await remove(SWITCH_MAC) is False
    assert await remove(WIRED_CLIENT_MAC) is True


@pytest.mark.usefixtures("network_config_entry_setup")
async def test_removed_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
) -> None:
    """The entities of a device that is no longer listed are removed."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE_URL}/devices", json=network_page([]))
    mock_network_requests()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    for entity_id in (
        RESTART_BUTTON,
        POWER_CYCLE_BUTTON,
        "sensor.switch_state",
        "sensor.switch_cpu_utilization",
    ):
        assert hass.states.get(entity_id) is None

    # Ports are fetched once per device, a removed device is not fetched again
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    assert hass.states.get(POWER_CYCLE_BUTTON) is None


async def test_unknown_device_state(
    hass: HomeAssistant,
    network_config_entry_factory: ConfigEntryFactoryType,
    network_device_payload: list[dict[str, Any]],
    network_device_details_payload: dict[str, dict[str, Any]],
) -> None:
    """A device state this version does not know reads as unknown."""
    network_device_payload[:] = [{**SWITCH, "state": "NEW_STATE"}]
    network_device_details_payload[SWITCH_ID] = {**SWITCH_DETAILS, "state": "NEW_STATE"}

    await network_config_entry_factory()

    assert hass.states.get("sensor.switch_state").state == STATE_UNKNOWN


ACCESS_POINT_ID = "5ff3bc5f-6d39-3d2e-9bfd-0f2bf6c3f1d5"
ACCESS_POINT = {
    **SWITCH,
    "features": ["accessPoint"],
    "id": ACCESS_POINT_ID,
    "macAddress": "00:00:00:00:01:02",
    "model": "U7 Pro",
    "name": "Access point",
}


async def test_device_data_of_one_device_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_config_entry_factory: ConfigEntryFactoryType,
    network_device_payload: list[dict[str, Any]],
    network_device_statistics_payload: dict[str, dict[str, Any]],
) -> None:
    """A device whose details fail does not hold up the others."""
    network_device_payload.append(ACCESS_POINT)
    network_device_statistics_payload[ACCESS_POINT_ID] = {}
    aioclient_mock.get(f"{SITE_URL}/devices/{ACCESS_POINT_ID}", status=500)

    await network_config_entry_factory()

    assert hass.states.get(POWER_CYCLE_BUTTON).state == STATE_UNKNOWN
    assert hass.states.get("sensor.switch_uptime").state != STATE_UNKNOWN
    assert hass.states.get("sensor.access_point_uptime").state == STATE_UNKNOWN


async def test_device_data_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_config_entry_factory: ConfigEntryFactoryType,
    network_device_statistics_payload: dict[str, dict[str, Any]],
) -> None:
    """Statistics that fail for every device are not loaded."""
    network_device_statistics_payload.clear()
    aioclient_mock.get(f"{SITE_URL}/devices/{SWITCH_ID}/statistics/latest", status=500)

    await network_config_entry_factory()

    assert hass.states.get("sensor.switch_state").state == "online"
    assert hass.states.get("sensor.switch_cpu_utilization") is None


@pytest.mark.usefixtures("network_config_entry_setup")
async def test_connection_lost_and_restored(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
) -> None:
    """A console that stops answering is retried until it answers again."""
    aioclient_mock.clear_requests()
    for path in ("info", "sites", f"sites/{NETWORK_SITE_ID}/devices"):
        aioclient_mock.get(f"{NETWORK_URL}/{path}", exc=aiohttp.ClientError())
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.switch_state").state == STATE_UNAVAILABLE

    # The application answers with an error, there is no login to retry
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{NETWORK_URL}/info", status=500)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=MAX_RETRY_DELAY))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.switch_state").state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    mock_network_requests()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=2 * MAX_RETRY_DELAY)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.switch_state").state == "online"


async def test_rejected_key_while_polling_starts_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_config_entry_setup: MockConfigEntry,
) -> None:
    """A key that is no longer accepted asks for a new one."""
    aioclient_mock.clear_requests()
    for path in (
        "info",
        f"sites/{NETWORK_SITE_ID}/clients",
        f"sites/{NETWORK_SITE_ID}/devices",
    ):
        aioclient_mock.get(f"{NETWORK_URL}/{path}", status=401)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)

    for attempt in range(1, LOGIN_REJECTIONS_BEFORE_REAUTH):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=attempt * MAX_RETRY_DELAY)
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert any(network_config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    ("side_effect", "state", "reauth"),
    [
        (aiounifi.RequestError, ConfigEntryState.SETUP_RETRY, False),
        (aiounifi.Unauthorized, ConfigEntryState.SETUP_ERROR, True),
    ],
    ids=["unavailable", "rejected_key"],
)
async def test_assign_site_fails(
    hass: HomeAssistant,
    network_config_entry_factory: ConfigEntryFactoryType,
    side_effect: type[Exception],
    state: ConfigEntryState,
    reauth: bool,
) -> None:
    """A site that cannot be assigned is retried or asks for a new key."""
    with patch(
        "aiounifi.network.v1.api_client.ApiClient.assign_site", side_effect=side_effect
    ):
        config_entry = await network_config_entry_factory()

    assert config_entry.state is state
    assert any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})) is reauth


@pytest.mark.usefixtures("network_config_entry_setup")
async def test_new_device_failing_keeps_known_ports(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
) -> None:
    """Details of a new device that fail leave the known ports usable."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE_URL}/devices", json=network_page([SWITCH, ACCESS_POINT]))
    aioclient_mock.get(f"{SITE_URL}/devices/{ACCESS_POINT_ID}", status=500)
    aioclient_mock.get(
        f"{SITE_URL}/devices/{ACCESS_POINT_ID}/statistics/latest", json={}
    )
    mock_network_requests()
    # The device list lists the new device before its ports are fetched
    for seconds in (11, 61):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
        await hass.async_block_till_done()

    assert hass.states.get(POWER_CYCLE_BUTTON).state == STATE_UNKNOWN


async def test_unsupported_device(
    hass: HomeAssistant,
    network_config_entry_factory: ConfigEntryFactoryType,
    network_device_payload: list[dict[str, Any]],
    network_device_details_payload: dict[str, dict[str, Any]],
) -> None:
    """A device the Integration API does not support gets no entities."""
    network_device_payload[:] = [{**SWITCH, "supported": False}]
    network_device_details_payload.clear()

    await network_config_entry_factory()

    assert hass.states.get(RESTART_BUTTON) is None
    assert hass.states.get("sensor.switch_state") is None


@pytest.mark.usefixtures("network_config_entry_setup")
async def test_statistics_poll_between_device_polls(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
) -> None:
    """Device polls in between do not hold statistics back."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{SITE_URL}/devices/{SWITCH_ID}/statistics/latest",
        json={**SWITCH_STATISTICS, "cpuUtilizationPct": 50.0},
    )
    mock_network_requests()
    # A device poll in between must not move the statistics poll due at 60 s
    for seconds in (11, 61):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.switch_cpu_utilization").state == "50.0"


async def test_ports_of_only_device_fail(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_config_entry_factory: ConfigEntryFactoryType,
    network_device_details_payload: dict[str, dict[str, Any]],
) -> None:
    """A device whose details fail still gets its other entities."""
    network_device_details_payload.clear()
    aioclient_mock.get(f"{SITE_URL}/devices/{SWITCH_ID}", status=500)

    await network_config_entry_factory()

    assert hass.states.get(POWER_CYCLE_BUTTON) is None
    assert hass.states.get(RESTART_BUTTON) is not None


async def test_device_removed_while_statistics_are_fetched(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
    network_config_entry_setup: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Statistics of a device removed meanwhile are not stored."""
    devices = network_config_entry_setup.runtime_data.api.network.devices

    async def remove_device(
        method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        devices.reconcile([])
        return AiohttpClientMockResponse(method, url, json=SWITCH_STATISTICS)

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{SITE_URL}/devices/{SWITCH_ID}/statistics/latest", side_effect=remove_device
    )
    mock_network_requests()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert SWITCH_MAC not in network_config_entry_setup.runtime_data.network_statistics
    assert hass.states.get("sensor.switch_cpu_utilization") is None
    assert "Unexpected error" not in caplog.text


@pytest.mark.freeze_time("2026-11-07 10:05:00+00:00")
@pytest.mark.usefixtures("network_config_entry_setup")
async def test_uptime_from_sample_time(hass: HomeAssistant) -> None:
    """Uptime counts from when the statistics were sampled, not from now."""
    # Sampled at 10:00 with an hour of uptime
    assert hass.states.get("sensor.switch_uptime").state == "2026-11-07T09:00:00+00:00"
