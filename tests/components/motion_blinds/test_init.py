"""Test the Motionblinds setup."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from motionblinds import DEVICE_TYPES_GATEWAY, DEVICE_TYPES_WIFI, BlindType
from motionblinds.motion_blinds import DEVICE_TYPE_BLIND
import pytest

from homeassistant.components.motion_blinds.const import DEFAULT_INTERFACE, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

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
