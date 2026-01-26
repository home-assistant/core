"""Common fixtures for the BLE Battery Management System integration tests."""

from collections.abc import Awaitable, Buffer, Callable, Iterable
import logging
from typing import Any, Final
from uuid import UUID

from aiobmsble import BMSInfo, BMSSample, MatcherPattern
from aiobmsble.basebms import BaseBMS
from aiobmsble.utils import load_bms_plugins
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
from home_assistant_bluetooth import SOURCE_LOCAL, BluetoothServiceInfoBleak
import pytest

from homeassistant.components.bms_ble.const import DOMAIN

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

LOGGER: logging.Logger = logging.getLogger(__name__)


def pytest_addoption(parser) -> None:
    """Add custom command-line option for max_examples."""
    parser.addoption(
        "--max-examples",
        action="store",
        type=int,
        default=1000,
        help="Set the maximum number of examples for Hypothesis tests.",
    )


@pytest.fixture(params=[False, True])
def bool_fixture(request: pytest.FixtureRequest) -> bool:
    """Return False, True for tests."""
    return request.param


@pytest.fixture(
    params=[
        bms.__name__.rsplit(".", 1)[-1]
        for bms in sorted(
            load_bms_plugins(), key=lambda plugin: getattr(plugin, "__name__", "")
        )
    ]
)
def bms_fixture(request: pytest.FixtureRequest) -> str:
    """Return all possible BMS variants."""
    return request.param


@pytest.fixture
def patch_default_bleak_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch BleakClient to a mock as BT is not available.

    required because BTdiscovery cannot be used to generate a BleakClient in async_setup()
    """
    monkeypatch.setattr("aiobmsble.basebms.BleakClient", MockBleakClient)


@pytest.fixture
def patch_entity_enabled_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Entity.entity_registry_enabled_default to always return True."""

    monkeypatch.setattr(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        lambda _: True,
    )


@pytest.fixture
def bt_discovery() -> BluetoothServiceInfoBleak:
    """Return a valid Bluetooth object for testing."""
    DATA: Final[dict[str, Any]] = {
        "name": "SmartBat-B12345",
        "address": "cc:cc:cc:cc:cc:cc",
        "service_uuids": ["0000fff0-0000-1000-8000-00805f9b34fb"],
        "rssi": -61,
        "tx_power": -76,
    }

    return BluetoothServiceInfoBleak(
        name=DATA["name"],
        address=DATA["address"],
        device=generate_ble_device(
            address=DATA["address"],
            name=DATA["name"],
        ),
        rssi=DATA["rssi"],
        service_uuids=DATA["service_uuids"],
        manufacturer_data={},
        service_data={},
        advertisement=generate_advertisement_data(
            local_name=DATA["name"],
            service_uuids=DATA["service_uuids"],
            rssi=DATA["rssi"],
            tx_power=DATA["tx_power"],
        ),
        source=SOURCE_LOCAL,
        connectable=True,
        time=0,
        tx_power=DATA["tx_power"],
    )


# use inject_bluetooth_service_info
@pytest.fixture
def bt_discovery_notsupported() -> BluetoothServiceInfoBleak:
    """Return a Bluetooth object that describes a not supported device."""
    return BluetoothServiceInfoBleak(
        name="random",  # not supported name
        address="cc:cc:cc:cc:cc:cc",
        device=generate_ble_device(
            address="cc:cc:cc:cc:cc:cc",
            name="random",
        ),
        rssi=-61,
        service_uuids=[
            "b42e1c08-ade7-11e4-89d3-123b93f75cba",
        ],
        manufacturer_data={},
        service_data={},
        advertisement=generate_advertisement_data(local_name="random"),
        source="local",
        connectable=True,
        time=0,
        tx_power=-76,
    )


def mock_config(
    bms: str = "dummy_bms",
    unique_id: str | None = "cc:cc:cc:cc:cc:cc",
) -> MockConfigEntry:
    """Return a Mock of the HA entity config (latest version)."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=0,
        unique_id=unique_id,
        data={"type": f"aiobmsble.bms.{bms}"},
        title=f"config_test_{bms}",
    )


@pytest.fixture(params=[TimeoutError, BleakError, EOFError])
def mock_coordinator_exception(request: pytest.FixtureRequest) -> Exception:
    """Return possible exceptions for mock BMS update function."""
    return request.param


class MockBMS(BaseBMS):
    """Mock Battery Management System."""

    INFO: BMSInfo = {
        "default_manufacturer": "Mock Manufacturer",
        "default_model": "MockBMS",
    }

    def __init__(
        self, exc: Exception | None = None, ret_value: BMSSample | None = None
    ) -> None:  # , ble_device, keep_alive: bool = True
        """Initialize BMS."""
        super().__init__(generate_ble_device(address="", details={"path": None}), True)
        LOGGER.debug("%s init(), Test except: %s", MockBMS.bms_id(), str(exc))
        self._exception: Exception | None = exc
        self._ret_value: BMSSample = (
            ret_value
            if ret_value is not None
            else {
                "voltage": 13,
                "current": 1.7,
                "cycle_charge": 19,
                "cycles": 23,
            }
        )  # set fixed values for dummy battery

    @staticmethod
    def matcher_dict_list() -> list[MatcherPattern]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "mock", "connectable": True}]

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of services required by BMS."""
        return [normalize_uuid_str("cafe")]

    @staticmethod
    def uuid_rx() -> str:
        """Return characteristic that provides notification/read property."""
        return "feed"

    @staticmethod
    def uuid_tx() -> str:
        """Return characteristic that provides write property."""
        return "cafe"

    def _notification_handler(
        self, sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Retrieve BMS data update."""

    # async def disconnect(self) -> None:
    #     """Disconnect connection to BMS if active."""

    async def _async_update(self) -> BMSSample:
        """Update battery status information."""
        await self._connect()

        if self._exception:
            raise self._exception

        return self._ret_value


class MockBleakClient(BleakClient):
    """Mock bleak client."""

    def __init__(
        self,
        address_or_ble_device: BLEDevice,
        disconnected_callback: Callable[[BleakClient], None] | None,
        services: Iterable[str] | None = None,
        **kwargs,
    ) -> None:
        """Mock init."""
        LOGGER.debug("MockBleakClient init")
        super().__init__(
            address_or_ble_device.address
        )  # call with address to avoid backend resolving
        self._connected: bool = False
        self._notify_callback: (
            Callable[[BleakGATTCharacteristic, bytearray], None | Awaitable[None]]
            | None
        ) = None
        self._disconnect_callback: Callable[[BleakClient], None] | None = (
            disconnected_callback
        )
        self._ble_device: BLEDevice = address_or_ble_device
        self._services: Iterable[str] | None = services

    @property
    def address(self) -> str:
        """Return device address."""
        return self._ble_device.address

    @property
    def is_connected(self) -> bool:
        """Mock connected."""
        return self._connected

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Mock GATT services."""
        return BleakGATTServiceCollection()

    async def connect(self, *_args, **_kwargs) -> None:
        """Mock connect."""
        assert not self._connected, "connect called, but client already connected."
        LOGGER.debug("MockBleakClient connecting %s", self._ble_device.address)
        self._connected = True

    async def start_notify(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        callback: Callable[
            [BleakGATTCharacteristic, bytearray], None | Awaitable[None]
        ],
        **kwargs,
    ) -> None:
        """Mock start_notify."""
        LOGGER.debug("MockBleakClient start_notify for %s", char_specifier)
        assert self._connected, "start_notify called, but client not connected."
        self._notify_callback = callback

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Mock write GATT characteristics."""
        LOGGER.debug(
            "MockBleakClient write_gatt_char %s, data: %s", char_specifier, data
        )
        assert self._connected, "write_gatt_char called, but client not connected."

    async def read_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        **kwargs,
    ) -> bytearray:
        """Mock write GATT characteristics."""
        LOGGER.debug("MockBleakClient read_gatt_char %s", char_specifier)
        assert self._connected, "read_gatt_char called, but client not connected."
        return bytearray()

    async def disconnect(self) -> None:
        """Mock disconnect."""

        LOGGER.debug("MockBleakClient disconnecting %s", self._ble_device.address)
        self._connected = False
        if self._disconnect_callback is not None:
            self._disconnect_callback(self)


async def mock_update_min(_self) -> BMSSample:
    """Minimal version of a BMS update to mock initial coordinator update."""
    return {"voltage": 12.3, "battery_charging": False}


async def mock_update_full(self) -> BMSSample:
    """Include optional sensors for BMS update to mock initial coordinator update."""
    return await mock_update_min(self) | {
        "problem": False,
        "balancer": 0x0,
        "battery_charging": True,
        "battery_health": 73,
        "chrg_mosfet": False,
        "dischrg_mosfet": False,
        "heater": False,
    }


async def mock_exception(_self) -> BMSSample:
    """Failing version of a BMS update to mock initial coordinator update."""
    raise BleakError


async def mock_devinfo_min(_self) -> BMSInfo:
    """Minimal version of a BMS device info to mock initial coordinator update."""
    return {"manufacturer": "Mock manufacturer"}
