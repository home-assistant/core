"""Diagnostics tests for the Inepro Metering integration."""

from datetime import UTC, datetime
import importlib

from inepro_metering.const import MeterFamily, TransportType
from inepro_metering.runtime import MeterRoute, build_meter_runtime_data

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.inepro_metering.const import (
    CONF_ACTIVE_ROUTE,
    CONF_BAUDRATE,
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_BYTESIZE,
    CONF_FAMILY,
    CONF_METERS,
    CONF_PARITY,
    CONF_ROUTE_PURPOSE,
    CONF_ROUTES,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TIMEOUT,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    ROUTE_PURPOSE_ACTIVE,
    ROUTE_PURPOSE_ONBOARDING,
)
from homeassistant.components.inepro_metering.coordinator import (
    CoordinatorData,
    MeterCoordinatorData,
    SerialBusCoordinatorData,
)
import homeassistant.components.inepro_metering.diagnostics as diagnostics_module
from homeassistant.components.inepro_metering.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.inepro_metering.models import get_profile
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class _FakeSingleCoordinator:
    """Small diagnostics stub for one single-meter entry."""

    def __init__(self, data: CoordinatorData) -> None:
        self.data = data
        self.last_update_success = True
        self.last_exception = None


class _FakeBusCoordinator:
    """Small diagnostics stub for one shared-bus entry."""

    def __init__(self, data: SerialBusCoordinatorData) -> None:
        self.data = data
        self.last_update_success = True
        self.last_exception = None


async def test_config_entry_diagnostics_redact_secrets_and_summarize_runtime(
    hass: HomeAssistant,
) -> None:
    """Diagnostics should redact secrets and expose only summary runtime data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            "scan_interval": 15,
            "host": "192.168.68.80",
            "port": 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 3,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    "host": "192.168.68.80",
                    "port": 502,
                }
            ],
            CONF_ACTIVE_ROUTE: "tcp_ethernet:192.168.68.80:502:1",
        },
        options={
            "ssid": "OfficeWiFi",
            "password": "super-secret",
            "pairing_code": "123456",
        },
        version=5,
    )
    entry.add_to_hass(hass)

    runtime = build_meter_runtime_data(
        profile=get_profile(MeterFamily.GROW.value, "grow_750"),
        route=MeterRoute(
            transport=TransportType.TCP_ETHERNET,
            slave_id=1,
        ),
        readings={
            "serial_number": "075625480002",
            "product_code": "0756",
            "meter_code": "0756",
            "software_version": 1.2,
            "modbus_product_name": "GROW 3P4S",
            "modbus_device_version": "1.2.0",
        },
        available=True,
        last_successful_update=datetime(2026, 4, 23, 11, 0, tzinfo=UTC),
    )
    entry.runtime_data = _FakeSingleCoordinator(CoordinatorData(meter=runtime))

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["options"]["ssid"] == REDACTED
    assert result["entry"]["options"]["password"] == REDACTED
    assert result["entry"]["options"]["pairing_code"] == REDACTED
    assert result["transport"]["active_route_key"] == "tcp_ethernet:192.168.68.80:502:1"
    assert result["runtime"]["meters"][0]["identity"]["serial_number"] == "075625480002"
    assert result["runtime"]["meters"][0]["firmware"]["software_version"] == "1.2.0"
    assert result["runtime"]["meters"][0]["readings"]["count"] == 6
    assert result["coordinator"]["snapshot"]["reading_count"] == 6


async def test_config_entry_diagnostics_include_bus_routes_and_snapshot(
    hass: HomeAssistant,
) -> None:
    """Diagnostics should describe shared-bus routes without dumping raw values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main RS485 Bus",
        unique_id="COM5",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            "scan_interval": 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "075625480002",
                    "product_code": "0756",
                    CONF_ROUTES: [
                        {
                            CONF_TRANSPORT: TransportType.SERIAL.value,
                            CONF_SLAVE_ID: 1,
                            CONF_TIMEOUT: 3,
                            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                            CONF_SERIAL_PORT: "COM5",
                            CONF_BAUDRATE: DEFAULT_BAUDRATE,
                            CONF_BYTESIZE: DEFAULT_BYTESIZE,
                            CONF_PARITY: DEFAULT_PARITY,
                            CONF_STOPBITS: DEFAULT_STOPBITS,
                        },
                        {
                            CONF_TRANSPORT: TransportType.BLUETOOTH_PROXY.value,
                            CONF_SLAVE_ID: 1,
                            CONF_TIMEOUT: 5,
                            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ONBOARDING,
                            "host": "127.0.0.1",
                            "port": 16026,
                            CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66",
                            CONF_BLUETOOTH_NAME: "IM-075625480002",
                        },
                    ],
                    CONF_ACTIVE_ROUTE: "bluetooth_proxy:127.0.0.1:16026:11:22:33:44:55:66:1",
                }
            ],
        },
        version=5,
    )
    entry.add_to_hass(hass)

    runtime = build_meter_runtime_data(
        profile=get_profile(MeterFamily.GROW.value, "grow_750"),
        route=MeterRoute(
            transport=TransportType.BLUETOOTH_PROXY,
            slave_id=1,
        ),
        readings={
            "serial_number": "075625480002",
            "product_code": "0756",
            "meter_code": "0756",
        },
        available=True,
        last_successful_update=datetime(2026, 4, 23, 11, 30, tzinfo=UTC),
    )
    entry.runtime_data = _FakeBusCoordinator(
        SerialBusCoordinatorData(
            meters={
                "075625480002": MeterCoordinatorData(meter=runtime),
            }
        )
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    meter_transport = result["transport"]["meters"][0]
    assert meter_transport["meter_key"] == "075625480002"
    assert meter_transport["active_route_key"].startswith("bluetooth_proxy:")
    assert len(meter_transport["available_routes"]) == 2
    assert result["runtime"]["meters"][0]["route"]["transport"] == "bluetooth_proxy"
    assert result["coordinator"]["snapshot"]["meter_count"] == 1
    assert result["coordinator"]["snapshot"]["available_meters"] == ["075625480002"]


async def test_diagnostics_helpers_are_runtime_covered(
    hass: HomeAssistant,
) -> None:
    """Exercise diagnostics helper branches after a runtime reload."""
    reloaded_module = importlib.reload(diagnostics_module)

    assert reloaded_module._format_datetime(None) is None
    assert reloaded_module._transport_endpoint(
        {
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SERIAL_PORT: "COM5",
            CONF_SLAVE_ID: 2,
            CONF_TIMEOUT: 4,
        }
    ) == {
        "transport": TransportType.SERIAL.value,
        "serial_port": "COM5",
        "slave_id": 2,
        "timeout": 4,
    }
    assert reloaded_module._transport_endpoint(
        {
            CONF_TRANSPORT: TransportType.BLUETOOTH_PROXY.value,
            CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66",
            CONF_BLUETOOTH_NAME: "IM-075625480002",
            "host": "127.0.0.1",
            "port": 16026,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 5,
        }
    ) == {
        "transport": TransportType.BLUETOOTH_PROXY.value,
        "bluetooth_address": "11:22:33:44:55:66",
        "bluetooth_name": "IM-075625480002",
        "host": "127.0.0.1",
        "port": 16026,
        "slave_id": 1,
        "timeout": 5,
    }
    assert reloaded_module._transport_endpoint(
        {
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            "host": "192.168.68.80",
            "port": 502,
            CONF_SLAVE_ID: 3,
            CONF_TIMEOUT: 6,
        }
    ) == {
        "transport": TransportType.TCP_GATEWAY.value,
        "host": "192.168.68.80",
        "port": 502,
        "slave_id": 3,
        "timeout": 6,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 3,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    "host": "192.168.68.80",
                    "port": 502,
                }
            ],
            CONF_ACTIVE_ROUTE: "tcp_ethernet:192.168.68.80:502:1",
        },
        version=5,
    )
    entry.add_to_hass(hass)

    runtime = build_meter_runtime_data(
        profile=get_profile(MeterFamily.GROW.value, "grow_750"),
        route=MeterRoute(
            transport=TransportType.TCP_ETHERNET,
            slave_id=1,
        ),
        readings={
            "serial_number": "075625480002",
            "product_code": "0756",
            "meter_code": "0756",
        },
        available=True,
        last_successful_update=datetime(2026, 4, 23, 11, 0, tzinfo=UTC),
    )
    coordinator = _FakeSingleCoordinator(CoordinatorData(meter=runtime))
    entry.runtime_data = coordinator

    result = await diagnostics_module.async_get_config_entry_diagnostics(hass, entry)
    assert result["transport"]["entry_transport"] == TransportType.TCP_ETHERNET.value
    assert result["runtime"]["meters"][0]["meter_key"] == "075625480002"

    route = diagnostics_module.get_configured_routes(dict(entry.data))[0]
    assert diagnostics_module._serialize_route(route)["route_key"] == (
        "tcp_ethernet:192.168.68.80:502:1"
    )
    assert diagnostics_module._build_runtime_diagnostics(entry, None) is None
    assert diagnostics_module._build_runtime_diagnostics(
        entry,
        _FakeSingleCoordinator(data=object()),
    ) is None
    assert diagnostics_module._build_runtime_diagnostics(entry, coordinator)["meters"][0][
        "configured_name"
    ] == "075625480002"
    assert diagnostics_module._build_coordinator_diagnostics(None) is None

    coordinator.last_update_success = False
    coordinator.last_exception = RuntimeError("boom")
    coordinator_diagnostics = diagnostics_module._build_coordinator_diagnostics(
        coordinator
    )
    assert coordinator_diagnostics["last_exception"] == "RuntimeError"
    assert coordinator_diagnostics["snapshot"]["meter_count"] == 1

    bus_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main RS485 Bus",
        unique_id="COM5",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "075625480002",
                    CONF_ROUTES: [
                        {
                            CONF_TRANSPORT: TransportType.SERIAL.value,
                            CONF_SLAVE_ID: 1,
                            CONF_TIMEOUT: 3,
                            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                            CONF_SERIAL_PORT: "COM5",
                            CONF_BAUDRATE: DEFAULT_BAUDRATE,
                            CONF_BYTESIZE: DEFAULT_BYTESIZE,
                            CONF_PARITY: DEFAULT_PARITY,
                            CONF_STOPBITS: DEFAULT_STOPBITS,
                        },
                        {
                            CONF_TRANSPORT: TransportType.BLUETOOTH_PROXY.value,
                            CONF_SLAVE_ID: 1,
                            CONF_TIMEOUT: 5,
                            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ONBOARDING,
                            "host": "127.0.0.1",
                            "port": 16026,
                            CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66",
                            CONF_BLUETOOTH_NAME: "IM-075625480002",
                        },
                    ],
                    CONF_ACTIVE_ROUTE: "bluetooth_proxy:127.0.0.1:16026:11:22:33:44:55:66:1",
                }
            ],
        },
        version=5,
    )
    bus_entry.add_to_hass(hass)

    bus_runtime = build_meter_runtime_data(
        profile=get_profile(MeterFamily.GROW.value, "grow_750"),
        route=MeterRoute(
            transport=TransportType.BLUETOOTH_PROXY,
            slave_id=1,
        ),
        readings={"serial_number": "075625480002"},
        available=True,
        last_successful_update=datetime(2026, 4, 23, 11, 30, tzinfo=UTC),
    )
    bus_coordinator = _FakeBusCoordinator(
        SerialBusCoordinatorData(
            meters={
                "075625480002": MeterCoordinatorData(meter=bus_runtime),
            }
        )
    )
    bus_result = diagnostics_module._build_runtime_diagnostics(bus_entry, bus_coordinator)
    assert bus_result["meters"][0]["route"]["transport"] == "bluetooth_proxy"
    assert diagnostics_module._build_coordinator_diagnostics(bus_coordinator)[
        "snapshot"
    ]["available_meters"] == ["075625480002"]
    assert diagnostics_module._build_transport_diagnostics(bus_entry)["bus_entry"] is True
