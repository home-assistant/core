"""Test the Motionblinds setup."""

from collections.abc import Generator
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from motionblinds import DEVICE_TYPES_GATEWAY, DEVICE_TYPES_WIFI, BlindType
from motionblinds.motion_blinds import DEVICE_TYPE_BLIND
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.components.config import DOMAIN as CONFIG_DOMAIN
from homeassistant.components.motion_blinds import async_remove_config_entry_device
from homeassistant.components.motion_blinds.const import (
    DEFAULT_INTERFACE,
    DOMAIN,
    UPDATE_INTERVAL,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

TEST_HOST = "1.2.3.4"
TEST_API_KEY = "12ab345c-d67e-8f"
TEST_GATEWAY_MAC = "abcdefghijkl"
TEST_BLIND_MAC = "abcdefghijkl0001"


@pytest.fixture(name="mock_gateway")
def mock_gateway_fixture() -> Mock:
    """Return a mocked gateway with a single sub-blind."""
    blind = Mock()
    blind.mac = TEST_BLIND_MAC
    blind.device_type = DEVICE_TYPE_BLIND
    blind.type = BlindType.RollerBlind
    blind.blind_type = BlindType.RollerBlind.name
    blind.wireless_name = "RF"
    blind.battery_voltage = 0
    blind.limit_status = "Limit2Detected"
    blind.position = 0
    blind.angle = 0
    blind.RSSI = -50

    gateway = Mock()
    gateway.mac = TEST_GATEWAY_MAC
    gateway.device_type = DEVICE_TYPES_GATEWAY[0]
    gateway.firmware = "1.0.0"
    gateway.protocol = "1.0"
    gateway.device_list = {TEST_BLIND_MAC: blind}
    gateway.blind_type_list = {TEST_BLIND_MAC: BlindType.RollerBlind.value}

    blind._gateway = gateway
    return gateway


@pytest.fixture(name="mock_connect", autouse=True)
def mock_connect_fixture(mock_gateway: Mock) -> Generator[None]:
    """Mock the connection to the Motion gateway."""
    with (
        patch(
            "homeassistant.components.motion_blinds.coordinator.UPDATE_DELAY_BLIND", 0
        ),
        patch(
            "homeassistant.components.motion_blinds.AsyncMotionMulticast"
        ) as multicast_class,
        patch(
            "homeassistant.components.motion_blinds.ConnectMotionGateway"
        ) as connect_class,
    ):
        multicast_class.return_value.Start_listen = AsyncMock()
        connect = connect_class.return_value
        connect.async_check_interface = AsyncMock(return_value=DEFAULT_INTERFACE)
        connect.async_connect_gateway = AsyncMock(return_value=True)
        connect.gateway_device = mock_gateway
        yield


@pytest.mark.parametrize(
    "gateway_device_type",
    [
        pytest.param(DEVICE_TYPES_GATEWAY[0], id="reported-gateway-type"),
        pytest.param(DEVICE_TYPES_WIFI[0], id="unexpected-non-gateway-type"),
    ],
)
async def test_sub_blind_links_to_gateway_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_gateway: Mock,
    gateway_device_type: str,
) -> None:
    """Test that a sub-blind device links to the gateway device as its parent.

    The gateway device must be registered up front even when the gateway
    self-reports a device_type outside DEVICE_TYPES_GATEWAY, so RF (non-Wi-Fi)
    blinds can still resolve it as their via_device parent.
    """
    mock_gateway.device_type = gateway_device_type

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_MAC,
        data={CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    gateway_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_GATEWAY_MAC), entry.entry_id
    )
    blind_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_BLIND_MAC), entry.entry_id
    )

    assert gateway_device is not None
    assert blind_device is not None
    assert blind_device.via_device_id == gateway_device.id


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("cover.rollerblind_0001", id="cover"),
        pytest.param("sensor.rollerblind_0001_signal_strength", id="sensor"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_gateway: Mock,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test entities become unavailable when a coordinator update fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_MAC,
        data={CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_gateway.Update.side_effect = OSError("Network unreachable")
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_gateway.Update.side_effect = None
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("identifier", "expected_result"),
    [
        pytest.param(TEST_GATEWAY_MAC, False, id="gateway"),
        pytest.param(TEST_BLIND_MAC, False, id="connected-blind"),
        pytest.param("old_blind", True, id="stale-blind"),
    ],
)
async def test_remove_config_entry_device_via_websocket(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    identifier: str,
    expected_result: bool,
) -> None:
    """Test device removal through the device-registry WebSocket API."""
    assert await async_setup_component(hass, CONFIG_DOMAIN, {})
    ws_client: MockHAClientWebSocket = await hass_ws_client(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_MAC,
        data={CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "old_blind")},
    )

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), entry.entry_id
    )
    assert device_entry is not None

    await ws_client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": device_entry.id}
    )
    response = await ws_client.receive_json()

    assert response["success"] is expected_result
    assert (device_registry.async_get(device_entry.id) is None) is expected_result


async def test_remove_config_entry_device_without_runtime_data(
    hass: HomeAssistant,
) -> None:
    """Test that a device cannot be removed when runtime data is unavailable."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    device_entry = SimpleNamespace(identifiers={(DOMAIN, "old_blind")})

    assert not await async_remove_config_entry_device(hass, config_entry, device_entry)
