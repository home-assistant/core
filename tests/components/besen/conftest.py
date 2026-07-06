"""Fixtures for the Besen integration tests."""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, patch

from besen.client import BesenClient
from besen.models import BesenData, ChargerConfig, ChargerInfo, ChargeStatus
import pytest

from homeassistant.components.besen import PLATFORMS
from homeassistant.components.besen.const import DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN, Platform
from homeassistant.core import HomeAssistant

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


@dataclass
class BesenClientFixture:
    """Mocked Besen client and helpers."""

    client: Mock
    constructor: Mock
    remove_listener: Mock
    listeners: list[Callable[[BesenData], None]]

    def publish_state(self, state: BesenData) -> None:
        """Publish a state update from the mocked client."""

        self.client.state = state
        for listener in list(self.listeners):
            listener(state)


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


def _create_client_mock() -> Mock:
    """Create a mocked Besen client instance."""

    client = Mock(spec=BesenClient)
    client.address = FIXTURE_ADDRESS
    client.state = charger_state()
    client.async_start = AsyncMock()
    client.async_stop = AsyncMock()
    client.async_start_charging = AsyncMock()
    client.async_stop_charging = AsyncMock()
    return client


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


@pytest.fixture
def mock_besen_client() -> Generator[BesenClientFixture]:
    """Patch the integration Besen client."""

    client = _create_client_mock()
    listeners: list[Callable[[BesenData], None]] = []
    remove_listener = Mock()

    def add_listener(
        listener: Callable[[BesenData], None],
    ) -> Callable[[], None]:
        listeners.append(listener)

        def remove() -> None:
            remove_listener()
            if listener in listeners:
                listeners.remove(listener)

        return remove

    client.add_listener.side_effect = add_listener

    with patch(
        "homeassistant.components.besen.BesenClient",
        return_value=client,
    ) as constructor:
        fixture = BesenClientFixture(
            client=client,
            constructor=constructor,
            remove_listener=remove_listener,
            listeners=listeners,
        )

        async def async_start_charging() -> None:
            fixture.publish_state(charger_state(charger_status=True))

        async def async_stop_charging() -> None:
            fixture.publish_state(charger_state(charger_status=False))

        client.async_start_charging.side_effect = async_start_charging
        client.async_stop_charging.side_effect = async_stop_charging
        yield fixture


@pytest.fixture
def mock_validation_client() -> Generator[BesenClientFixture]:
    """Patch the config flow Besen client."""

    client = _create_client_mock()
    with patch(
        "homeassistant.components.besen.config_flow.BesenClient",
        return_value=client,
    ) as constructor:
        yield BesenClientFixture(
            client=client,
            constructor=constructor,
            remove_listener=Mock(),
            listeners=[],
        )


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
