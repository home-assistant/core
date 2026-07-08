"""Fixtures for the Besen integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from besen.models import BesenData, ChargerConfig, ChargerInfo, ChargeStatus
import pytest

from homeassistant.components.besen import PLATFORMS
from homeassistant.components.besen.const import DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN, Platform
from homeassistant.core import HomeAssistant

from . import publish_besen_state

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

FIXTURE_ADDRESS = "AA:BB"
FIXTURE_DISCOVERY_ADDRESS = "aa:bb"
FIXTURE_NAME = "ACP#Garage"
FIXTURE_PIN = "123456"

FAKE_BLE_DEVICE = generate_ble_device(
    address=FIXTURE_DISCOVERY_ADDRESS,
    name=FIXTURE_NAME,
)

FAKE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=FIXTURE_NAME,
    address=FIXTURE_DISCOVERY_ADDRESS,
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=FAKE_BLE_DEVICE,
    advertisement=generate_advertisement_data(
        local_name=FIXTURE_NAME,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)


def charger_state(
    *,
    charger_status: bool | None = True,
    available: bool = True,
    authenticated: bool = True,
) -> BesenData:
    """Return a populated charger state."""

    return BesenData(
        info=ChargerInfo(
            address=FIXTURE_ADDRESS,
            serial="SERIAL",
            phases=1,
            manufacturer="Besen",
            model="BS20",
            hardware_version="HW1",
            software_version="SW1",
        ),
        config=ChargerConfig(device_name="Garage", rssi=-55),
        charge=ChargeStatus(
            charger_status=charger_status,
            current_energy=3500,
            total_energy=1.2,
            current_amount=12.3,
            inner_temp_c=24.5,
        ),
        available=available,
        authenticated=authenticated,
    )


def _configure_client_mock(client: Mock) -> None:
    """Configure a mocked Besen client instance."""

    client.address = FIXTURE_ADDRESS
    client.state = charger_state()
    client.async_start = AsyncMock()
    client.async_stop = AsyncMock()
    client.async_start_charging = AsyncMock()
    client.async_stop_charging = AsyncMock()
    client.add_listener.return_value = Mock()


@pytest.fixture(autouse=True)
def mock_ble_device(enable_bluetooth: None) -> Generator[Mock]:
    """Mock Bluetooth helpers."""

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=FAKE_BLE_DEVICE,
        ) as mock_ble_device,
        patch(
            "homeassistant.components.bluetooth.async_request_active_scan",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bluetooth.async_address_reachability_diagnostics",
            return_value="diagnostic reason",
        ),
    ):
        yield mock_ble_device


@pytest.fixture(autouse=True)
def mock_discovered_service_info(enable_bluetooth: None) -> Generator[Mock]:
    """Mock discovered Bluetooth devices."""

    with patch(
        "homeassistant.components.besen.config_flow.async_discovered_service_info",
        return_value=[FAKE_SERVICE_INFO],
    ) as mock_discovered_service_info:
        yield mock_discovered_service_info


@pytest.fixture
def mock_besen_client() -> Generator[Mock]:
    """Patch the integration Besen client."""

    with (
        patch(
            "homeassistant.components.besen.BesenClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.besen.config_flow.BesenClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        _configure_client_mock(client)

        async def async_start_charging() -> None:
            publish_besen_state(client, charger_state(charger_status=True))

        async def async_stop_charging() -> None:
            publish_besen_state(client, charger_state(charger_status=False))

        client.async_start_charging.side_effect = async_start_charging
        client.async_stop_charging.side_effect = async_stop_charging
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a config entry mock."""

    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: FIXTURE_ADDRESS,
            CONF_NAME: FIXTURE_NAME,
            CONF_PIN: FIXTURE_PIN,
        },
        title="Garage",
        unique_id=FIXTURE_ADDRESS,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Patch integration setup after a config flow creates an entry."""

    with patch(
        "homeassistant.components.besen.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


async def setup_with_selected_platforms(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    platforms: list[Platform] | None = None,
) -> None:
    """Set up the Besen integration with selected platforms."""

    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.besen.PLATFORMS",
        platforms or PLATFORMS,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
