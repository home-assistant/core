"""Home Assistant config flow tests for Inepro Metering."""

from ipaddress import ip_address
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from inepro_metering.const import MeterFamily, TransportType
import pytest

from homeassistant.components.inepro_metering import async_migrate_entry
from homeassistant.components.inepro_metering.bluetooth import (
    DiscoveredGrowBluetoothMeter,
)
from homeassistant.components.inepro_metering.config_flow import (
    CONF_DISCOVERED_BLUETOOTH_METER,
    CONF_SELECTED_METER,
    CONF_SELECTED_ROUTE,
    IneproIdentityError,
    _async_validate_entry_identity,
)
from homeassistant.components.inepro_metering.config_flow_schemas import (
    UNSELECTED_TRANSPORT,
    build_add_route_bluetooth_discovered_schema,
    build_add_route_connection_schema,
    build_bluetooth_confirm_schema,
    build_bluetooth_discovered_schema,
    build_connection_schema,
    build_gateway_scan_schema,
    build_update_connection_schema,
)
from homeassistant.components.inepro_metering.config_flow_shared import (
    CONF_BLUETOOTH_PAIRING_PIN,
    CONF_RESET_BLUETOOTH_PAIRING,
    bluetooth_setup_identity_error_reason,
    bluetooth_validation_error_reason,
)
from homeassistant.components.inepro_metering.const import (
    CONF_ACTIVE_ROUTE,
    CONF_BAUDRATE,
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_BYTESIZE,
    CONF_DEVICE_KIND,
    CONF_DISCOVERED_GATEWAY,
    CONF_FAMILY,
    CONF_GATEWAY_DISCOVERY_TARGET,
    CONF_GATEWAY_SETUP_METHOD,
    CONF_METERS,
    CONF_PARITY,
    CONF_ROUTE_PURPOSE,
    CONF_ROUTES,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_SETUP_METHOD,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DEFAULT_BAUDRATE,
    DEFAULT_BLE_PROXY_HOST,
    DEFAULT_BLE_PROXY_PORT,
    DEFAULT_BLUETOOTH_SCAN_INTERVAL,
    DEFAULT_BLUETOOTH_TIMEOUT,
    DEFAULT_BYTESIZE,
    DEFAULT_GATEWAY_SCAN_SLAVE_ID_END,
    DEFAULT_PARITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOPBITS,
    DEFAULT_TIMEOUT,
    DEVICE_KIND_GATEWAY,
    DOMAIN,
    GATEWAY_SETUP_METHOD_MANUAL_IP,
    GATEWAY_SETUP_METHOD_SCAN_NETWORK,
    ROUTE_PURPOSE_ACTIVE,
    ROUTE_PURPOSE_ONBOARDING,
    SETUP_METHOD_MANUAL,
    SETUP_METHOD_SCAN_BLUETOOTH,
    SETUP_METHOD_SCAN_SERIAL,
    SETUP_METHOD_SCAN_TCP_GATEWAY,
)
from homeassistant.components.inepro_metering.discovery import (
    DiscoveredGrowMeter,
    DiscoveredTcpGateway,
)
from homeassistant.components.inepro_metering.entry_data import (
    build_route_key,
    get_configured_routes,
)
from homeassistant.components.inepro_metering.modbus import (
    BLUETOOTH_PAIRING_MODE_NEVER,
    CONF_BLUETOOTH_FORCE_REPAIR,
    CONF_BLUETOOTH_PAIRING_MODE,
    CONF_BLUETOOTH_PAIRING_TIMEOUT,
    IneproBluetoothNotPairedError,
    IneproConnectionError,
)
from homeassistant.components.inepro_metering.models import RegisterType
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

EDIT_SERIAL_BUS_DYNAMIC_CONFIG_FIELD_TRANSLATIONS = [
    "component.inepro_metering.config.step.edit_serial_bus.data.Modbus ID for 080125260007",
    "component.inepro_metering.config.step.edit_serial_bus.data.Modbus ID for 085125250008",
    "component.inepro_metering.config.step.edit_serial_bus.data_description.Modbus ID for 080125260007",
    "component.inepro_metering.config.step.edit_serial_bus.data_description.Modbus ID for 085125250008",
]
EDIT_SERIAL_BUS_DYNAMIC_OPTIONS_FIELD_TRANSLATIONS = [
    "component.inepro_metering.options.step.edit_serial_bus.data.Modbus ID for 080125260007",
    "component.inepro_metering.options.step.edit_serial_bus.data.Modbus ID for 085125250008",
    "component.inepro_metering.options.step.edit_serial_bus.data_description.Modbus ID for 080125260007",
    "component.inepro_metering.options.step.edit_serial_bus.data_description.Modbus ID for 085125250008",
]


def _raise_identity_error_from(cause: BaseException) -> None:
    """Raise an identity error from the supplied cause."""
    raise IneproConnectionError("Failed to validate meter identity") from cause


@pytest.fixture(autouse=True)
def mock_config_flow_entry_setup(request):
    """Avoid real transport setup for entries created by config flows."""
    if "real_entry_setup" in request.fixturenames:
        yield
        return

    with patch(
        "homeassistant.components.inepro_metering.async_setup_entry",
        new=AsyncMock(return_value=True),
    ):
        yield


@pytest.fixture
def real_entry_setup() -> None:
    """Allow a test to exercise the integration setup path."""


def test_bluetooth_validation_error_reason_maps_encryption_trigger() -> None:
    """Raw encrypted-write backend errors should ask for host-level pairing."""
    try:
        _raise_identity_error_from(
            RuntimeError("GATT Protocol Error: Insufficient Encryption")
        )
    except IneproConnectionError as err:
        reason = bluetooth_validation_error_reason(err, TransportType.BLUETOOTH)

    assert reason == "bluetooth_not_paired"


def test_bluetooth_validation_error_reason_maps_ble_modbus_timeout() -> None:
    """Silent encrypted-write timeouts should ask for host-level pairing."""
    try:
        _raise_identity_error_from(
            TimeoutError(
                "Timed out waiting for BLE Modbus response from IM-075625480002"
            )
        )
    except IneproConnectionError as err:
        reason = bluetooth_validation_error_reason(err, TransportType.BLUETOOTH)

    assert reason == "bluetooth_not_paired"


def test_bluetooth_validation_error_reason_keeps_generic_failure_unclassified() -> None:
    """Only setup identity validation should upgrade generic BLE read failures."""
    err = IneproConnectionError("Failed to validate meter identity")

    assert bluetooth_validation_error_reason(err, TransportType.BLUETOOTH) == (
        "cannot_validate"
    )
    assert bluetooth_setup_identity_error_reason(err, TransportType.BLUETOOTH) == (
        "bluetooth_not_paired"
    )


def _expected_serial_route(
    *,
    serial_port: str,
    slave_id: int,
    timeout: int,
    baudrate: int = DEFAULT_BAUDRATE,
    bytesize: int = DEFAULT_BYTESIZE,
    parity: str = DEFAULT_PARITY,
    stopbits: int = DEFAULT_STOPBITS,
    purpose: str = ROUTE_PURPOSE_ACTIVE,
) -> dict[str, object]:
    """Build the expected serialized shared-bus serial route."""
    return {
        CONF_TRANSPORT: TransportType.SERIAL.value,
        CONF_SLAVE_ID: slave_id,
        CONF_TIMEOUT: timeout,
        CONF_ROUTE_PURPOSE: purpose,
        CONF_SERIAL_PORT: serial_port,
        CONF_BAUDRATE: baudrate,
        CONF_BYTESIZE: bytesize,
        CONF_PARITY: parity,
        CONF_STOPBITS: stopbits,
    }


def _expected_gateway_route(
    *,
    host: str,
    port: int,
    slave_id: int,
    timeout: int,
    purpose: str = ROUTE_PURPOSE_ACTIVE,
) -> dict[str, object]:
    """Build the expected serialized shared-bus gateway route."""
    return {
        CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
        CONF_SLAVE_ID: slave_id,
        CONF_TIMEOUT: timeout,
        CONF_ROUTE_PURPOSE: purpose,
        CONF_HOST: host,
        CONF_PORT: port,
    }


def _zeroconf_info(
    *,
    service_type: str = "_modbus._tcp.local.",
    name: str = "inepro_075625480002._modbus._tcp.local.",
    hostname: str = "inepro_075625480002.local.",
    address: str = "192.168.68.76",
    port: int | None = 502,
    properties: dict[str, object] | None = None,
) -> ZeroconfServiceInfo:
    """Build one Home Assistant Zeroconf service info object."""
    parsed_address = ip_address(address)
    return ZeroconfServiceInfo(
        ip_address=parsed_address,
        ip_addresses=[parsed_address],
        port=port,
        hostname=hostname,
        type=service_type,
        name=name,
        properties=(
            {
                "model": "879-3120",
                "serial": "075625480002",
                "vendor": "WAGO GmbH & Co. KG",
            }
            if properties is None
            else properties
        ),
    )


def _expected_bus_meter(
    *,
    family: str,
    name: str,
    variant: str,
    slave_id: int,
    timeout: int,
    transport: TransportType = TransportType.SERIAL,
    serial_port: str | None = None,
    host: str | None = None,
    port: int = 502,
    serial_number: str | None = None,
    product_code: str | None = None,
    baudrate: int = DEFAULT_BAUDRATE,
    bytesize: int = DEFAULT_BYTESIZE,
    parity: str = DEFAULT_PARITY,
    stopbits: int = DEFAULT_STOPBITS,
) -> dict[str, object]:
    """Build the expected serialized shared-bus meter structure."""
    if transport is TransportType.SERIAL:
        assert serial_port is not None
        routes = [
            _expected_serial_route(
                serial_port=serial_port,
                slave_id=slave_id,
                timeout=timeout,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
            )
        ]
        active_route = f"serial:{serial_port.upper()}:{slave_id}"
    else:
        assert host is not None
        routes = [
            _expected_gateway_route(
                host=host,
                port=port,
                slave_id=slave_id,
                timeout=timeout,
            )
        ]
        active_route = f"tcp_gateway:{host.lower()}:{port}:{slave_id}"

    data: dict[str, object] = {
        CONF_FAMILY: family,
        CONF_NAME: name,
        CONF_VARIANT: variant,
        CONF_SLAVE_ID: slave_id,
        CONF_ROUTES: routes,
        CONF_ACTIVE_ROUTE: active_route,
    }
    if serial_number is not None:
        data[CONF_SERIAL_NUMBER] = serial_number
    if product_code is not None:
        data["product_code"] = product_code
    return data


def _schema_field_names(schema) -> set[str]:
    """Return the submitted field names from a voluptuous schema."""
    return {getattr(field, "schema", field) for field in schema.schema}


def _schema_field(schema, field_name: str):
    """Return one marker from a voluptuous schema by submitted field name."""
    return next(
        field for field in schema.schema if getattr(field, "schema", None) == field_name
    )


def _schema_selector(schema, field_name: str):
    """Return one selector from a voluptuous schema by submitted field name."""
    return schema.schema[_schema_field(schema, field_name)]


async def _finish_progress(hass, result):
    """Advance a progress result to the next visible flow step."""
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        return await hass.config_entries.flow.async_configure(result["flow_id"])
    return result


async def test_zeroconf_with_serial_and_wago_vendor_creates_tcp_meter(
    hass,
) -> None:
    """A GROW mDNS service with TXT serial and WAGO vendor should be accepted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            name="plant-meter._modbus._tcp.local.",
            hostname="plant-meter.local.",
            port=1502,
            properties={
                "serial": "075625480002",
                "vendor": "WAGO GmbH & Co. KG",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert _schema_field_names(result["data_schema"]) == {CONF_TRANSPORT}
    transport_selector = _schema_selector(result["data_schema"], CONF_TRANSPORT)
    assert {option["value"] for option in transport_selector.config["options"]} == {
        UNSELECTED_TRANSPORT,
        TransportType.TCP_WIFI.value,
        TransportType.TCP_ETHERNET.value,
    }

    validate_modbus = AsyncMock()
    validate_identity = AsyncMock()
    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=validate_modbus,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TRANSPORT: TransportType.TCP_WIFI.value},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "075625480002"
    assert result["data"][CONF_SERIAL_NUMBER] == "075625480002"
    assert result["data"][CONF_HOST] == "192.168.68.76"
    assert result["data"][CONF_PORT] == 1502
    assert result["data"][CONF_TRANSPORT] == TransportType.TCP_WIFI.value
    assert result["data"][CONF_VARIANT] == "grow_750"
    assert result["data"][CONF_ACTIVE_ROUTE] == "tcp_wifi:192.168.68.76:1502:1"
    validate_modbus.assert_awaited_once()
    assert (
        validate_modbus.await_args.args[0][CONF_TRANSPORT]
        == TransportType.TCP_WIFI.value
    )
    validate_identity.assert_awaited_once()
    assert (
        validate_identity.await_args.args[0][CONF_TRANSPORT]
        == TransportType.TCP_WIFI.value
    )


async def test_zeroconf_confirm_can_store_discovered_endpoint_as_ethernet(
    hass,
) -> None:
    """The mDNS endpoint should keep its host/port with the selected TCP transport."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            address="192.168.68.76",
            port=502,
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TRANSPORT: TransportType.TCP_ETHERNET.value},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.68.76"
    assert result["data"][CONF_PORT] == 502
    assert result["data"][CONF_TRANSPORT] == TransportType.TCP_ETHERNET.value
    assert result["data"][CONF_ACTIVE_ROUTE] == "tcp_ethernet:192.168.68.76:502:1"
    route_keys = [
        build_route_key(route) for route in get_configured_routes(result["data"])
    ]
    assert route_keys == ["tcp_ethernet:192.168.68.76:502:1"]


async def test_zeroconf_confirm_requires_ethernet_or_wifi_selection(
    hass,
) -> None:
    """A discovered Modbus TCP endpoint should not silently become Wi-Fi."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
        new=AsyncMock(),
    ) as validate_modbus:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TRANSPORT: UNSELECTED_TRANSPORT},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "transport_required"}
    validate_modbus.assert_not_awaited()


async def test_zeroconf_with_serial_and_known_model_accepts_custom_hostname(
    hass,
) -> None:
    """Hostname branding is only a hint; TXT serial plus known model is enough."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            name="custom-meter._modbus._tcp.local.",
            hostname="plant-room-meter.local.",
            properties={
                "serial": "075625480002",
                "model": "879-3120",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


async def test_zeroconf_uses_txt_serial_as_unique_id(
    hass,
) -> None:
    """Duplicate protection should use the TXT serial, not IP or hostname."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_HOST: "192.168.68.50",
            CONF_PORT: 502,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            hostname="renamed-meter.local.",
            address="192.168.68.76",
            port=1502,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.68.76"
    assert entry.data[CONF_PORT] == 1502


async def test_zeroconf_duplicate_with_changed_port_updates_direct_entry(
    hass,
) -> None:
    """A rediscovered direct TCP meter should refresh its endpoint before aborting."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            name="custom-grow-name._modbus._tcp.local.",
            hostname="custom-grow-name.local.",
            address="192.168.68.90",
            port=1502,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.68.90"
    assert entry.data[CONF_PORT] == 1502


async def test_zeroconf_rediscovery_updates_direct_route_data(
    hass,
) -> None:
    """Zeroconf rediscovery should keep route data consistent with top-level data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                },
                {
                    CONF_TRANSPORT: TransportType.BLUETOOTH_PROXY.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ONBOARDING,
                    CONF_HOST: DEFAULT_BLE_PROXY_HOST,
                    CONF_PORT: DEFAULT_BLE_PROXY_PORT,
                    CONF_BLUETOOTH_ADDRESS: "80:F1:B2:58:DD:5A",
                    CONF_BLUETOOTH_NAME: "IM-075625480002",
                },
                {
                    CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ONBOARDING,
                    CONF_HOST: "192.168.68.85",
                    CONF_PORT: 502,
                },
            ],
            CONF_ACTIVE_ROUTE: "tcp_wifi:192.168.68.76:502:1",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            address="192.168.68.90",
            port=1502,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.68.90"
    assert entry.data[CONF_PORT] == 1502
    assert entry.data[CONF_ACTIVE_ROUTE] == "tcp_wifi:192.168.68.90:1502:1"
    assert entry.data[CONF_ROUTES][0][CONF_HOST] == "192.168.68.90"
    assert entry.data[CONF_ROUTES][0][CONF_PORT] == 1502
    assert entry.data[CONF_ROUTES][1][CONF_HOST] == DEFAULT_BLE_PROXY_HOST
    assert entry.data[CONF_ROUTES][1][CONF_PORT] == DEFAULT_BLE_PROXY_PORT
    assert entry.data[CONF_ROUTES][2][CONF_HOST] == "192.168.68.85"
    assert entry.data[CONF_ROUTES][2][CONF_PORT] == 502


async def test_zeroconf_rediscovery_preserves_active_alternate_tcp_route(
    hass,
) -> None:
    """Zeroconf should not revert a manually selected active TCP route."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_HOST: "192.168.68.88",
            CONF_PORT: 502,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                },
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.88",
                    CONF_PORT: 502,
                },
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                },
            ],
            CONF_ACTIVE_ROUTE: "tcp_wifi:192.168.68.88:502:1",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            address="192.168.68.76",
            port=502,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.68.88"
    assert entry.data[CONF_PORT] == 502
    assert entry.data[CONF_ACTIVE_ROUTE] == "tcp_wifi:192.168.68.88:502:1"
    route_keys = [build_route_key(route) for route in get_configured_routes(entry.data)]
    assert route_keys == [
        "tcp_wifi:192.168.68.76:502:1",
        "tcp_wifi:192.168.68.88:502:1",
    ]


async def test_zeroconf_rediscovery_collapses_direct_tcp_endpoint_conflict(
    hass,
) -> None:
    """Zeroconf should not keep stale Wi-Fi/Ethernet labels for one endpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                },
                {
                    CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                },
            ],
            CONF_ACTIVE_ROUTE: "tcp_ethernet:192.168.68.76:502:1",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            address="192.168.68.76",
            port=502,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.68.76"
    assert entry.data[CONF_PORT] == 502
    assert entry.data[CONF_ACTIVE_ROUTE] == "tcp_ethernet:192.168.68.76:502:1"
    assert [build_route_key(route) for route in get_configured_routes(entry.data)] == [
        "tcp_ethernet:192.168.68.76:502:1",
    ]


async def test_zeroconf_legacy_entry_updates_host_port(
    hass,
) -> None:
    """Legacy direct entries should update by stored serial even with endpoint unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.68.76:502",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                }
            ],
            CONF_ACTIVE_ROUTE: "tcp_wifi:192.168.68.76:502:1",
        },
    )
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_update_entry",
        wraps=hass.config_entries.async_update_entry,
    ) as update_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=_zeroconf_info(
                address="192.168.68.90",
                port=1502,
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    update_entry.assert_called_once()
    assert update_entry.call_args.args[0] is entry
    assert entry.unique_id == "192.168.68.76:502"
    assert entry.data[CONF_HOST] == "192.168.68.90"
    assert entry.data[CONF_PORT] == 1502
    assert entry.data[CONF_ACTIVE_ROUTE] == "tcp_wifi:192.168.68.90:1502:1"
    assert entry.data[CONF_ROUTES][0][CONF_HOST] == "192.168.68.90"
    assert entry.data[CONF_ROUTES][0][CONF_PORT] == 1502


async def test_zeroconf_duplicate_via_gateway_does_not_update_gateway_entry(
    hass,
) -> None:
    """A meter already behind a gateway should not become a direct TCP entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.68.85:502",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "Inepro Gateway 033023260133",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_HOST: "192.168.68.85",
            CONF_PORT: 502,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    CONF_NAME: "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SERIAL_NUMBER: "075625480002",
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_ROUTES: [
                        {
                            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
                            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                            CONF_TIMEOUT: DEFAULT_TIMEOUT,
                            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                            CONF_HOST: "192.168.68.85",
                            CONF_PORT: 502,
                        }
                    ],
                    CONF_ACTIVE_ROUTE: "tcp_gateway:192.168.68.85:502:1",
                }
            ],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            address="192.168.68.90",
            port=1502,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_via_gateway"
    assert entry.data[CONF_HOST] == "192.168.68.85"
    assert entry.data[CONF_PORT] == 502
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_zeroconf_rejects_modbus_service_without_serial(
    hass,
) -> None:
    """TXT serial is required even when the hostname looks like an inepro meter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            properties={"vendor": "WAGO GmbH & Co. KG", "model": "879-3120"},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_zeroconf_rejects_modbus_service_without_ownership_hint(
    hass,
) -> None:
    """A serial on an unrelated Modbus mDNS service is not enough."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            name="generic-meter._modbus._tcp.local.",
            hostname="generic-meter.local.",
            properties={
                "serial": "075625480002",
                "vendor": "Other Vendor",
                "model": "unknown",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_zeroconf_rejects_unrelated_service_type(
    hass,
) -> None:
    """Only Modbus TCP mDNS services should enter the GROW discovery path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(service_type="_http._tcp.local."),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_zeroconf_accepts_case_insensitive_txt_keys(
    hass,
) -> None:
    """TXT keys should tolerate common case differences."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            name="custom-meter._modbus._tcp.local.",
            hostname="custom-meter.local.",
            properties={
                "Serial": "075625480002",
                "Vendor": "WAGO GmbH & Co. KG",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


async def test_zeroconf_confirm_requires_live_identity_match(
    hass,
) -> None:
    """Zeroconf setup should validate that Modbus identity matches TXT serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(port=1502),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    validate_identity = AsyncMock(return_value=None)
    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TRANSPORT: TransportType.TCP_WIFI.value},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SERIAL_NUMBER] == "075625480002"
    assert result["data"][CONF_PORT] == 1502
    validate_identity.assert_awaited_once()
    validated_data = validate_identity.await_args.args[0]
    assert validated_data[CONF_SERIAL_NUMBER] == "075625480002"
    assert validated_data[CONF_HOST] == "192.168.68.76"
    assert validated_data[CONF_PORT] == 1502
    assert validated_data[CONF_TRANSPORT] == TransportType.TCP_WIFI.value


async def test_zeroconf_confirm_rejects_live_identity_mismatch(
    hass,
) -> None:
    """A TXT serial that does not match the live Modbus serial must not create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(side_effect=IneproIdentityError),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TRANSPORT: TransportType.TCP_WIFI.value},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "invalid_identity"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_zeroconf_confirm_reports_identity_read_failure(
    hass,
) -> None:
    """If the endpoint connects but serial cannot be read, keep the flow open."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(),
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(side_effect=IneproConnectionError),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TRANSPORT: TransportType.TCP_WIFI.value},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "cannot_validate"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_user_flow_can_choose_gateway_before_any_meter_details(
    hass,
) -> None:
    """The first config step should allow starting from a TCP gateway."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_setup_method"


async def test_user_flow_still_accepts_legacy_family_submission(
    hass,
) -> None:
    """The first step should remain tolerant of the older family-first submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_method"


async def test_gateway_manual_ip_path_opens_gateway_meter_scan(
    hass,
) -> None:
    """Known gateway IPs should jump straight to the downstream meter scan form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_MANUAL_IP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_scan"


async def test_gateway_network_scan_allows_explicit_target_retry(
    hass,
) -> None:
    """Gateway discovery should allow retrying with one explicit IP or subnet target."""
    discovered_gateway = DiscoveredTcpGateway(
        host="10.5.2.1",
        serial_number="033023260122",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_tcp_gateways",
        new=AsyncMock(return_value=(discovered_gateway,)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_SCAN_NETWORK},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "gateway_discover"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_DISCOVERY_TARGET: "10.5.2.1"},
        )
        result = await _finish_progress(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_discovered"


async def test_gateway_network_scan_shows_progress(
    hass,
) -> None:
    """Gateway discovery should use Home Assistant progress UI while scanning."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_tcp_gateways",
        new=AsyncMock(return_value=()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_SCAN_NETWORK},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "gateway_discover"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_DISCOVERY_TARGET: ""},
        )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "gateway_discover"
    assert result["progress_action"] == "gateway_discover"


async def test_gateway_network_scan_no_verified_gateways_shows_retry_form(
    hass,
) -> None:
    """Gateway discovery failures should return to the target form with guidance."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_tcp_gateways",
        new=AsyncMock(return_value=()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_SCAN_NETWORK},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_DISCOVERY_TARGET: ""},
        )
        result = await _finish_progress(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_discover"
    assert result["errors"] == {"base": "no_gateways_found"}


async def test_multiple_verified_gateways_can_be_selected(
    hass,
) -> None:
    """Gateway selections should include host and port for clear labels."""
    discovered_gateways = (
        DiscoveredTcpGateway(host="10.5.2.1", port=502, serial_number="GW-1"),
        DiscoveredTcpGateway(host="10.5.2.2", port=1502, serial_number="GW-2"),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_tcp_gateways",
        new=AsyncMock(return_value=discovered_gateways),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_SCAN_NETWORK},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "gateway_discover"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_DISCOVERY_TARGET: ""},
        )
        result = await _finish_progress(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_discovered"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DISCOVERED_GATEWAY: "10.5.2.2:1502"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_scan"
    port_field = next(
        field
        for field in result["data_schema"].schema
        if getattr(field, "schema", None) == CONF_PORT
    )
    assert port_field.default() == 1502


async def test_gateway_network_scan_rejects_invalid_explicit_target(
    hass,
) -> None:
    """Gateway discovery should surface validation errors for malformed scan targets."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_tcp_gateways",
        new=AsyncMock(side_effect=ValueError("bad target")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_SCAN_NETWORK},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_GATEWAY_DISCOVERY_TARGET: "not-a-network"},
        )
        result = await _finish_progress(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_discover"
    assert result["errors"] == {"base": "invalid_scan_target"}


async def test_gateway_can_be_added_when_no_downstream_meters_are_found(
    hass,
) -> None:
    """A validated gateway should not fail setup only because no meters were found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_MANUAL_IP},
    )

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_tcp_gateway",
        new=AsyncMock(return_value=()),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "10.5.2.2",
                CONF_PORT: 502,
                CONF_TIMEOUT: 3,
                "slave_id_start": 1,
                "slave_id_end": 8,
                CONF_SCAN_INTERVAL: 15,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_no_meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Inepro Gateway 10.5.2.2:502"
    assert result["data"][CONF_TRANSPORT] == TransportType.TCP_GATEWAY.value
    assert result["data"][CONF_HOST] == "10.5.2.2"
    assert result["data"][CONF_PORT] == 502
    assert result["data"][CONF_METERS] == []


async def test_gateway_scan_skips_meter_already_configured_directly_by_serial(
    hass,
) -> None:
    """Gateway scan must not offer a physical meter already configured directly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_MANUAL_IP},
    )

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_tcp_gateway",
        new=AsyncMock(
            return_value=(
                DiscoveredGrowMeter(
                    serial_number="075625480002",
                    slave_id=1,
                    variant="grow_750",
                    model_title="GROW 750",
                    family=MeterFamily.GROW,
                    product_code="0756",
                ),
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.68.85",
                CONF_PORT: 502,
                CONF_TIMEOUT: 3,
                "slave_id_start": 1,
                "slave_id_end": 8,
                CONF_SCAN_INTERVAL: 15,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_no_meters"


def test_gateway_scan_schema_defaults_to_fast_common_range() -> None:
    """Manual gateway scans should default to a fast common downstream range."""
    schema = build_gateway_scan_schema(None)
    slave_id_end_field = next(
        field
        for field in schema.schema
        if getattr(field, "schema", None) == "slave_id_end"
    )
    assert slave_id_end_field.default() == DEFAULT_GATEWAY_SCAN_SLAVE_ID_END


async def test_grow_850_gateway_support_still_allows_serial_manual_flow(
    hass,
) -> None:
    """GROW 850 should expose a transport choice while still allowing serial setup."""
    assert DEFAULT_PARITY == "E"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_MANUAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Lab Meter",
            CONF_VARIANT: "grow_850",
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.SERIAL.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_read_detected_grow_serial",
            new=AsyncMock(return_value="085125250008"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SERIAL_PORT: "COM7",
                CONF_BAUDRATE: DEFAULT_BAUDRATE,
                CONF_BYTESIZE: DEFAULT_BYTESIZE,
                CONF_PARITY: DEFAULT_PARITY,
                CONF_STOPBITS: DEFAULT_STOPBITS,
                CONF_TIMEOUT: 5,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lab Meter"
    assert result["data"][CONF_TRANSPORT] == TransportType.SERIAL.value
    assert result["data"][CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="Lab Meter",
            variant="grow_850",
            slave_id=DEFAULT_SLAVE_ID,
            serial_port="COM7",
            timeout=5,
            serial_number="085125250008",
            product_code="0851",
        )
    ]


async def test_grow_701_requires_transport_selection(
    hass,
) -> None:
    """Models with multiple transports should show the transport step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_MANUAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Main Meter",
            CONF_VARIANT: "grow_701",
            CONF_SLAVE_ID: 3,
            CONF_SCAN_INTERVAL: 20,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"


async def test_grow_manual_flow_hides_windows_ble_proxy_transport(
    hass,
) -> None:
    """Normal setup should not expose the developer-only Windows BLE proxy."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_MANUAL},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "BLE Proxy Meter",
            CONF_VARIANT: "grow_750",
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"

    transport_selector = next(
        selector
        for field, selector in result["data_schema"].schema.items()
        if getattr(field, "schema", None) == CONF_TRANSPORT
    )
    transport_options = {
        option["value"] for option in transport_selector.config["options"]
    }
    assert TransportType.BLUETOOTH_PROXY.value not in transport_options
    assert transport_options >= {
        TransportType.SERIAL.value,
        TransportType.TCP_GATEWAY.value,
        TransportType.BLUETOOTH.value,
        TransportType.TCP_WIFI.value,
        TransportType.TCP_ETHERNET.value,
    }


async def test_transport_step_requires_explicit_selection(
    hass,
) -> None:
    """The transport step should not silently default to the first option."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.PRO.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "PRO380 Gateway",
            CONF_VARIANT: "pro_380",
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: UNSELECTED_TRANSPORT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"
    assert result["errors"] == {"base": "transport_required"}


def test_bluetooth_confirm_schema_defaults_to_slower_polling() -> None:
    """Bluetooth-discovered meters should default to a calmer polling interval."""
    schema = build_bluetooth_confirm_schema(None)
    scan_interval_field = _schema_field(schema, CONF_SCAN_INTERVAL)
    timeout_field = _schema_field(schema, CONF_TIMEOUT)
    assert scan_interval_field.default() == DEFAULT_BLUETOOTH_SCAN_INTERVAL
    assert timeout_field.default() == DEFAULT_BLUETOOTH_TIMEOUT


def test_serial_connection_schema_defaults_to_standard_timeout() -> None:
    """Serial/RS-485 setup should keep the regular Modbus timeout default."""
    schema = build_connection_schema(TransportType.SERIAL, None)
    timeout_field = _schema_field(schema, CONF_TIMEOUT)

    assert timeout_field.default() == DEFAULT_TIMEOUT


def test_normal_bluetooth_schemas_do_not_offer_pin_or_reset() -> None:
    """Normal Bluetooth setup validates host-paired meters, not in-HA pairing."""
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="AA:BB:CC:DD:EE:FF",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-42,
    )
    schemas = (
        build_bluetooth_confirm_schema(None),
        build_bluetooth_discovered_schema((discovered_meter,), None),
        build_add_route_bluetooth_discovered_schema((discovered_meter,), None),
    )

    for schema in schemas:
        field_names = _schema_field_names(schema)
        assert CONF_BLUETOOTH_PAIRING_PIN not in field_names
        assert CONF_RESET_BLUETOOTH_PAIRING not in field_names


def test_add_route_bluetooth_schema_requires_long_ble_timeout() -> None:
    """Bluetooth route setup should not allow sub-10s BLE connection timeouts."""
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="AA:BB:CC:DD:EE:FF",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-42,
    )
    schema = build_add_route_bluetooth_discovered_schema((discovered_meter,), None)
    timeout_field = _schema_field(schema, CONF_TIMEOUT)
    timeout_selector = _schema_selector(schema, CONF_TIMEOUT)

    assert timeout_field.default() == DEFAULT_BLUETOOTH_TIMEOUT
    assert timeout_selector.config["min"] == 10


def test_manual_add_route_bluetooth_schema_requires_long_ble_timeout() -> None:
    """Manual Bluetooth route setup should keep the 10s BLE timeout floor."""
    schema = build_add_route_connection_schema(TransportType.BLUETOOTH, None)
    timeout_field = _schema_field(schema, CONF_TIMEOUT)
    timeout_selector = _schema_selector(schema, CONF_TIMEOUT)

    assert timeout_field.default() == DEFAULT_BLUETOOTH_TIMEOUT
    assert timeout_selector.config["min"] == DEFAULT_BLUETOOTH_TIMEOUT


def test_update_bluetooth_connection_schema_requires_long_ble_timeout() -> None:
    """Bluetooth update forms should not default below the BLE timeout floor."""
    schema = build_update_connection_schema(
        {
            CONF_TRANSPORT: TransportType.BLUETOOTH.value,
            CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_BLUETOOTH_NAME: "IM-075625480002",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        None,
    )
    timeout_field = _schema_field(schema, CONF_TIMEOUT)
    timeout_selector = _schema_selector(schema, CONF_TIMEOUT)

    assert timeout_field.default() == DEFAULT_BLUETOOTH_TIMEOUT
    assert timeout_selector.config["min"] == DEFAULT_BLUETOOTH_TIMEOUT


async def test_pro_380_flow_includes_transport_step_and_can_use_serial(
    hass,
) -> None:
    """PRO models should expose a transport step for serial vs gateway access."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.PRO.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "PRO Lab Meter",
            CONF_VARIANT: "pro_380",
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.SERIAL.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SERIAL_PORT: "COM9",
                CONF_BAUDRATE: DEFAULT_BAUDRATE,
                CONF_BYTESIZE: DEFAULT_BYTESIZE,
                CONF_PARITY: DEFAULT_PARITY,
                CONF_STOPBITS: DEFAULT_STOPBITS,
                CONF_TIMEOUT: 5,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PRO Lab Meter"
    assert result["data"][CONF_FAMILY] == MeterFamily.PRO.value
    assert result["data"][CONF_TRANSPORT] == TransportType.SERIAL.value
    assert result["data"][CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.PRO.value,
            name="PRO Lab Meter",
            variant="pro_380",
            slave_id=DEFAULT_SLAVE_ID,
            serial_port="COM9",
            timeout=5,
        )
    ]


async def test_grow_serial_scan_discovers_and_creates_entry(
    hass,
) -> None:
    """A GROW serial bus scan should create one shared serial bus entry."""
    discovered_meters = (
        DiscoveredGrowMeter(
            serial_number="075625480002",
            slave_id=7,
            variant="grow_750",
            model_title="GROW 3P4S",
            product_code="0756",
            meter_code="0756",
        ),
        DiscoveredGrowMeter(
            serial_number="085125250008",
            slave_id=157,
            variant="grow_850",
            model_title="GROW 1P1U",
            product_code="0851",
            meter_code="0851",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial_scan"

    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_serial_bus",
        new=AsyncMock(return_value=discovered_meters),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SERIAL_PORT: "COM5",
                CONF_BAUDRATE: DEFAULT_BAUDRATE,
                CONF_BYTESIZE: DEFAULT_BYTESIZE,
                CONF_PARITY: DEFAULT_PARITY,
                CONF_STOPBITS: DEFAULT_STOPBITS,
                CONF_TIMEOUT: 2,
                "slave_id_start": 1,
                "slave_id_end": 16,
                CONF_SCAN_INTERVAL: 15,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovered"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "discovered_meters": ["075625480002:7", "085125250008:157"],
            CONF_SCAN_INTERVAL: 20,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "075625480002"
    assert result["data"][CONF_TRANSPORT] == TransportType.SERIAL.value
    assert result["data"][CONF_SERIAL_PORT] == "COM5"
    assert result["data"][CONF_SCAN_INTERVAL] == 20
    assert result["data"][CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="075625480002",
            variant="grow_750",
            slave_id=7,
            serial_port="COM5",
            timeout=2,
            serial_number="075625480002",
            product_code="0756",
        ),
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="085125250008",
            variant="grow_850",
            slave_id=157,
            serial_port="COM5",
            timeout=2,
            serial_number="085125250008",
            product_code="0851",
        ),
    ]


async def test_grow_bluetooth_scan_discovers_and_creates_entry(
    hass,
) -> None:
    """A GROW Bluetooth scan should create a single BLE-backed meter entry."""
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="AA:BB:CC:DD:EE:FF",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-42,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
        return_value=(discovered_meter,),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_BLUETOOTH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_discovered"

    ble_device = SimpleNamespace(name="IM-075625480002", address="AA:BB:CC:DD:EE:FF")
    validate_gatt = AsyncMock(return_value="075625480002")
    validate_modbus = AsyncMock(return_value=None)
    validate_identity = AsyncMock(return_value=None)
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=validate_gatt,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=validate_modbus,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_DISCOVERED_BLUETOOTH_METER: "075625480002:AA:BB:CC:DD:EE:FF",
                CONF_SLAVE_ID: 1,
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
                CONF_SCAN_INTERVAL: 15,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "075625480002"
    assert result["data"][CONF_TRANSPORT] == TransportType.BLUETOOTH.value
    assert result["data"][CONF_BLUETOOTH_ADDRESS] == "AA:BB:CC:DD:EE:FF"
    assert result["data"][CONF_BLUETOOTH_NAME] == "IM-075625480002"
    assert result["data"][CONF_VARIANT] == "grow_750"
    assert result["data"][CONF_SERIAL_NUMBER] == "075625480002"
    assert result["data"][CONF_SLAVE_ID] == 1
    assert result["data"][CONF_TIMEOUT] == DEFAULT_BLUETOOTH_TIMEOUT
    validate_modbus.assert_not_awaited()
    assert (
        validate_identity.call_args.args[0][CONF_BLUETOOTH_PAIRING_MODE]
        == BLUETOOTH_PAIRING_MODE_NEVER
    )
    assert (
        validate_identity.call_args.args[0][CONF_TRANSPORT]
        == TransportType.BLUETOOTH.value
    )
    assert CONF_ROUTES not in validate_identity.call_args.args[0]
    assert CONF_ACTIVE_ROUTE not in validate_identity.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_TIMEOUT not in validate_identity.call_args.args[0]
    assert CONF_BLUETOOTH_FORCE_REPAIR not in validate_identity.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_PIN not in validate_identity.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_MODE not in validate_gatt.call_args.args[0]
    assert CONF_BLUETOOTH_FORCE_REPAIR not in validate_gatt.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_PIN not in validate_gatt.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_MODE not in result["data"]
    assert CONF_BLUETOOTH_FORCE_REPAIR not in result["data"]
    assert CONF_BLUETOOTH_PAIRING_PIN not in result["data"]


async def test_grow_bluetooth_scan_reports_not_paired(
    hass,
) -> None:
    """Bluetooth validation should ask for host pairing when FFE9 needs encryption."""
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="AA:BB:CC:DD:EE:FF",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-94,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
        return_value=(discovered_meter,),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_BLUETOOTH},
        )

    validate_identity = AsyncMock(side_effect=IneproBluetoothNotPairedError)
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=SimpleNamespace(
                name="IM-075625480002", address="AA:BB:CC:DD:EE:FF"
            ),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_DISCOVERED_BLUETOOTH_METER: "075625480002:AA:BB:CC:DD:EE:FF",
                CONF_SLAVE_ID: 1,
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
                CONF_SCAN_INTERVAL: 15,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_discovered"
    assert result["errors"] == {"base": "bluetooth_not_paired"}
    validate_identity.assert_awaited_once()


async def test_grow_bluetooth_scan_error_keeps_discovered_placeholders(
    hass,
) -> None:
    """Post-GATT BLE setup errors should keep placeholders and ask for pairing."""
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="AA:BB:CC:DD:EE:FF",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-94,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
        return_value=(discovered_meter,),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_BLUETOOTH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_discovered"
    assert result["description_placeholders"] == {"count": "1"}

    validate_modbus = AsyncMock(return_value=None)
    validate_identity = AsyncMock(side_effect=IneproConnectionError)
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=SimpleNamespace(
                name="IM-075625480002", address="AA:BB:CC:DD:EE:FF"
            ),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=validate_modbus,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_DISCOVERED_BLUETOOTH_METER: "075625480002:AA:BB:CC:DD:EE:FF",
                CONF_SLAVE_ID: 1,
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
                CONF_SCAN_INTERVAL: 30,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_discovered"
    assert result["errors"] == {"base": "bluetooth_not_paired"}
    assert result["description_placeholders"] == {"count": "1"}
    validate_modbus.assert_not_awaited()
    validate_identity.assert_awaited_once()
    assert validate_identity.call_args.args[0][CONF_BLUETOOTH_PAIRING_MODE] == (
        BLUETOOTH_PAIRING_MODE_NEVER
    )


async def test_grow_bluetooth_scan_does_not_fallback_to_windows_proxy(
    hass,
) -> None:
    """Normal Bluetooth scan should use HA Bluetooth only, not the developer proxy."""
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="80:F1:B2:58:DD:5A",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-52,
        transport=TransportType.BLUETOOTH_PROXY,
        proxy_host=DEFAULT_BLE_PROXY_HOST,
        proxy_port=DEFAULT_BLE_PROXY_PORT,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
            return_value=(),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_proxy_meters",
            new=AsyncMock(return_value=(discovered_meter,)),
        ) as proxy_scan,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_BLUETOOTH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_scan"
    assert result["errors"] == {"base": "no_bluetooth_devices_found"}
    proxy_scan.assert_not_awaited()


async def test_bluetooth_rediscovery_updates_direct_bluetooth_entry(
    hass,
) -> None:
    """Bluetooth rediscovery should refresh address/name for the same serial."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.BLUETOOTH.value,
            CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_BLUETOOTH_NAME: "IM-075625480002-OLD",
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_BLUETOOTH_SCAN_INTERVAL,
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.BLUETOOTH.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                    CONF_BLUETOOTH_NAME: "IM-075625480002-OLD",
                }
            ],
            CONF_ACTIVE_ROUTE: "bluetooth:AA:BB:CC:DD:EE:FF:1",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "bluetooth"},
        data=SimpleNamespace(
            name="IM-075625480002",
            address="11:22:33:44:55:66",
            rssi=-42,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_BLUETOOTH_ADDRESS] == "11:22:33:44:55:66"
    assert entry.data[CONF_BLUETOOTH_NAME] == "IM-075625480002"
    assert entry.data[CONF_ACTIVE_ROUTE] == "bluetooth:11:22:33:44:55:66:1"
    assert entry.data[CONF_ROUTES][0][CONF_BLUETOOTH_ADDRESS] == "11:22:33:44:55:66"


async def test_bluetooth_rediscovery_does_not_update_gateway_entry(
    hass,
) -> None:
    """A Bluetooth rediscovery must not overwrite a shared gateway entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.68.85:502",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "Inepro Gateway",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_HOST: "192.168.68.85",
            CONF_PORT: 502,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    CONF_NAME: "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SERIAL_NUMBER: "075625480002",
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                }
            ],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "bluetooth"},
        data=SimpleNamespace(
            name="IM-075625480002",
            address="11:22:33:44:55:66",
            rssi=-42,
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_via_gateway"
    assert entry.data[CONF_HOST] == "192.168.68.85"
    assert CONF_BLUETOOTH_ADDRESS not in entry.data


async def test_grow_bluetooth_scan_rejects_meter_already_on_gateway(
    hass,
) -> None:
    """User-triggered Bluetooth scan must not duplicate a gateway meter."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.68.85:502",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "Inepro Gateway",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_HOST: "192.168.68.85",
            CONF_PORT: 502,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    CONF_NAME: "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SERIAL_NUMBER: "075625480002",
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                }
            ],
        },
    )
    entry.add_to_hass(hass)
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="AA:BB:CC:DD:EE:FF",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-42,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
        return_value=(discovered_meter,),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_BLUETOOTH},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_discovered"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DISCOVERED_BLUETOOTH_METER: "075625480002:AA:BB:CC:DD:EE:FF",
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            CONF_SCAN_INTERVAL: 15,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_via_gateway"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert CONF_BLUETOOTH_ADDRESS not in entry.data


async def test_grow_bluetooth_scan_updates_legacy_direct_bluetooth_entry(
    hass,
) -> None:
    """User-triggered Bluetooth scan must not duplicate legacy serial entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:00",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.BLUETOOTH.value,
            CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:00",
            CONF_BLUETOOTH_NAME: "IM-075625480002-OLD",
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_BLUETOOTH_SCAN_INTERVAL,
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.BLUETOOTH.value,
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                    CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:00",
                    CONF_BLUETOOTH_NAME: "IM-075625480002-OLD",
                }
            ],
            CONF_ACTIVE_ROUTE: "bluetooth:AA:BB:CC:DD:EE:00:1",
        },
    )
    entry.add_to_hass(hass)
    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="AA:BB:CC:DD:EE:FF",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-42,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
        return_value=(discovered_meter,),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_BLUETOOTH},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DISCOVERED_BLUETOOTH_METER: "075625480002:AA:BB:CC:DD:EE:FF",
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            CONF_SCAN_INTERVAL: 15,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data[CONF_BLUETOOTH_ADDRESS] == "AA:BB:CC:DD:EE:FF"
    assert entry.data[CONF_BLUETOOTH_NAME] == "IM-075625480002"


async def test_grow_manual_flow_stores_detected_serial_number_even_when_renamed(
    hass,
) -> None:
    """Manual GROW setup should persist the detected serial independent of the UI name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_MANUAL},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Kitchen meter",
            CONF_VARIANT: "grow_750",
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.TCP_ETHERNET.value},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_read_detected_grow_serial",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.68.80",
                CONF_PORT: 502,
                CONF_TIMEOUT: 3,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kitchen meter"
    assert result["data"][CONF_SERIAL_NUMBER] == "075625480002"


async def test_grow_manual_flow_rejects_duplicate_detected_serial(
    hass,
) -> None:
    """Manual setup must not create another entry for an existing meter serial."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
        },
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_MANUAL},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Renamed meter",
            CONF_VARIANT: "grow_750",
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.TCP_ETHERNET.value},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_read_detected_grow_serial",
            new=AsyncMock(return_value="075625480002"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.68.90",
                CONF_PORT: 1502,
                CONF_TIMEOUT: 3,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_grow_manual_bluetooth_rejects_meter_already_on_gateway(
    hass,
) -> None:
    """Manual Bluetooth setup must not duplicate a gateway/shared-bus meter."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inepro Gateway",
        unique_id="192.168.68.85:502",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: "Inepro Gateway",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_HOST: "192.168.68.85",
            CONF_PORT: 502,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    CONF_NAME: "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SERIAL_NUMBER: "075625480002",
                    CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
                }
            ],
        },
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_MANUAL},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Renamed Bluetooth meter",
            CONF_VARIANT: "grow_750",
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.BLUETOOTH.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=SimpleNamespace(
                name="IM-075625480002",
                address="AA:BB:CC:DD:EE:FF",
            ),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_read_detected_grow_serial",
            new=AsyncMock(return_value="075625480002"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                CONF_BLUETOOTH_NAME: "IM-075625480002",
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["errors"] == {"base": "already_configured_via_gateway"}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_migrate_single_entry_stores_top_level_serial_number(hass) -> None:
    """Legacy single-meter entries should persist their serial in entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
        },
        version=2,
    )

    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 5
    assert entry.data[CONF_SERIAL_NUMBER] == "075625480002"
    assert entry.data[CONF_ACTIVE_ROUTE].startswith("tcp_ethernet:")
    assert entry.data[CONF_ROUTES] == [
        {
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 3,
            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
        }
    ]


async def test_validate_entry_identity_uses_stored_serial_number(
    hass,
) -> None:
    """Identity validation should use stored serial metadata instead of the entry name."""
    client = AsyncMock()
    client.async_read_registers = AsyncMock(return_value=[0x2548, 0x0002])
    client.async_close = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.inepro_metering.config_flow.IneproModbusClient",
        return_value=client,
    ):
        await _async_validate_entry_identity(
            {
                CONF_FAMILY: MeterFamily.GROW.value,
                CONF_NAME: "Kitchen meter",
                CONF_SERIAL_NUMBER: "075625480002",
                CONF_VARIANT: "grow_750",
                CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                CONF_SLAVE_ID: 1,
                CONF_HOST: "192.168.68.80",
                CONF_PORT: 502,
                CONF_TIMEOUT: 3,
            }
        )

    client.async_read_registers.assert_awaited_once_with(
        register_type=RegisterType.HOLDING,
        address=0x4000,
        count=2,
        slave_id=1,
    )
    client.async_close.assert_awaited_once()


async def test_grow_serial_scan_appends_new_meter_to_existing_bus(
    hass,
) -> None:
    """Scanning an existing bus should append newly found meters to that bus entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inepro Serial Bus COM5",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    "serial_number": "085125250008",
                    "product_code": "0851",
                }
            ],
        },
        version=2,
    )
    existing_entry.add_to_hass(hass)

    discovered_meter = DiscoveredGrowMeter(
        serial_number="075625480002",
        slave_id=157,
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        meter_code="0756",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_SERIAL},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_discover_grow_serial_bus",
            new=AsyncMock(return_value=(discovered_meter,)),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SERIAL_PORT: "COM5",
                CONF_BAUDRATE: DEFAULT_BAUDRATE,
                CONF_BYTESIZE: DEFAULT_BYTESIZE,
                CONF_PARITY: DEFAULT_PARITY,
                CONF_STOPBITS: DEFAULT_STOPBITS,
                CONF_TIMEOUT: 2,
                "slave_id_start": 1,
                "slave_id_end": 200,
                CONF_SCAN_INTERVAL: 20,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "discovered_meters": ["075625480002:157"],
                CONF_SCAN_INTERVAL: 20,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "meter_added_to_existing_bus"
    assert existing_entry.data[CONF_SCAN_INTERVAL] == 20
    assert existing_entry.data[CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="085125250008",
            variant="grow_850",
            slave_id=1,
            serial_port="COM5",
            timeout=3,
            serial_number="085125250008",
            product_code="0851",
        ),
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="075625480002",
            variant="grow_750",
            slave_id=157,
            serial_port="COM5",
            timeout=3,
            serial_number="075625480002",
            product_code="0756",
        ),
    ]


async def test_pro_manual_serial_flow_can_append_to_existing_grow_bus(
    hass,
) -> None:
    """Manual PRO setup should append to an existing shared serial bus entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main RS485 Bus",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "085125250008",
                    "product_code": "0851",
                }
            ],
        },
        version=4,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.PRO.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "PRO380 Lab",
            CONF_VARIANT: "pro_380",
            CONF_SLAVE_ID: 41,
            CONF_SCAN_INTERVAL: 15,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.SERIAL.value},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SERIAL_PORT: "COM5",
                CONF_BAUDRATE: DEFAULT_BAUDRATE,
                CONF_BYTESIZE: DEFAULT_BYTESIZE,
                CONF_PARITY: DEFAULT_PARITY,
                CONF_STOPBITS: DEFAULT_STOPBITS,
                CONF_TIMEOUT: 5,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "meter_added_to_existing_bus"
    assert existing_entry.data[CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="085125250008",
            variant="grow_850",
            slave_id=1,
            serial_port="COM5",
            timeout=3,
            serial_number="085125250008",
            product_code="0851",
        ),
        _expected_bus_meter(
            family=MeterFamily.PRO.value,
            name="PRO380 Lab",
            variant="pro_380",
            slave_id=41,
            serial_port="COM5",
            timeout=3,
        ),
    ]


async def test_serial_bus_options_flow_can_append_new_meter(
    hass,
) -> None:
    """The options flow should let an existing serial bus entry grow with new meters."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inepro Serial Bus COM5",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    "serial_number": "085125250008",
                    "product_code": "0851",
                }
            ],
        },
        version=2,
    )
    entry.add_to_hass(hass)

    discovered_meter = DiscoveredGrowMeter(
        serial_number="075625480002",
        slave_id=157,
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        meter_code="0756",
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "scan_serial"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial_bus_scan"

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_discover_grow_serial_bus",
            new=AsyncMock(return_value=(discovered_meter,)),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "slave_id_start": 1,
                "slave_id_end": 200,
                CONF_SCAN_INTERVAL: 20,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "serial_bus_discovered"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "discovered_meters": ["075625480002:157"],
                CONF_SCAN_INTERVAL: 20,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_SCAN_INTERVAL] == 20
    assert entry.data[CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="085125250008",
            variant="grow_850",
            slave_id=1,
            serial_port="COM5",
            timeout=3,
            serial_number="085125250008",
            product_code="0851",
        ),
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="075625480002",
            variant="grow_750",
            slave_id=157,
            serial_port="COM5",
            timeout=3,
            serial_number="075625480002",
            product_code="0756",
        ),
    ]


async def test_grow_gateway_scan_flow_can_create_shared_gateway_bus(
    hass,
) -> None:
    """Scanning a TCP gateway should create one shared Modbus bus entry."""
    discovered_meter = DiscoveredGrowMeter(
        serial_number="075625480002",
        slave_id=7,
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        meter_code="0756",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.GROW.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SETUP_METHOD: SETUP_METHOD_SCAN_TCP_GATEWAY},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_discover_grow_tcp_gateway",
            new=AsyncMock(return_value=(discovered_meter,)),
        ),
        patch(
            "homeassistant.components.inepro_metering.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "10.5.2.14",
                CONF_PORT: 502,
                CONF_TIMEOUT: 3,
                "slave_id_start": 1,
                "slave_id_end": 32,
                CONF_SCAN_INTERVAL: 30,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "discovered"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "discovered_meters": ["075625480002:7"],
                CONF_SCAN_INTERVAL: 30,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TRANSPORT] == TransportType.TCP_GATEWAY.value
    assert result["data"][CONF_HOST] == "10.5.2.14"
    assert result["data"][CONF_PORT] == 502
    assert result["data"][CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="075625480002",
            variant="grow_750",
            slave_id=7,
            transport=TransportType.TCP_GATEWAY,
            host="10.5.2.14",
            port=502,
            timeout=3,
            serial_number="075625480002",
            product_code="0756",
        )
    ]


async def test_gateway_device_scan_flow_can_create_pro_shared_gateway_bus(
    hass,
) -> None:
    """Adding a gateway directly should create a PRO shared-bus entry."""
    discovered_meter = DiscoveredGrowMeter(
        serial_number="025423266355",
        slave_id=5,
        variant="pro_1",
        model_title="PRO1",
        product_code="0254",
        family=MeterFamily.PRO,
        meter_code="0101",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_KIND: DEVICE_KIND_GATEWAY},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GATEWAY_SETUP_METHOD: GATEWAY_SETUP_METHOD_MANUAL_IP},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_discover_grow_tcp_gateway",
            new=AsyncMock(return_value=(discovered_meter,)),
        ),
        patch(
            "homeassistant.components.inepro_metering.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "10.5.2.2",
                CONF_PORT: 502,
                CONF_TIMEOUT: 3,
                "slave_id_start": 1,
                "slave_id_end": DEFAULT_GATEWAY_SCAN_SLAVE_ID_END,
                CONF_SCAN_INTERVAL: 30,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "discovered"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "discovered_meters": ["025423266355:5"],
                CONF_SCAN_INTERVAL: 30,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FAMILY] == MeterFamily.PRO.value
    assert result["data"][CONF_TRANSPORT] == TransportType.TCP_GATEWAY.value
    assert result["data"][CONF_HOST] == "10.5.2.2"
    assert result["data"][CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.PRO.value,
            name="025423266355",
            variant="pro_1",
            slave_id=5,
            transport=TransportType.TCP_GATEWAY,
            host="10.5.2.2",
            port=502,
            timeout=3,
            serial_number="025423266355",
            product_code="0254",
        )
    ]


async def test_pro_manual_gateway_flow_can_append_to_existing_gateway_bus(
    hass,
) -> None:
    """Manual PRO setup should append to an existing shared TCP gateway bus entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gateway bus",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "10.5.2.14",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "085125250008",
                    "product_code": "0851",
                }
            ],
        },
        version=5,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FAMILY: MeterFamily.PRO.value},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "PRO380 Gateway",
            CONF_VARIANT: "pro_380",
            CONF_SLAVE_ID: 41,
            CONF_SCAN_INTERVAL: 15,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.TCP_GATEWAY.value},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "10.5.2.14",
                CONF_PORT: 502,
                CONF_TIMEOUT: 5,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "meter_added_to_existing_bus"
    assert existing_entry.data[CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="085125250008",
            variant="grow_850",
            slave_id=1,
            transport=TransportType.TCP_GATEWAY,
            host="10.5.2.14",
            port=502,
            timeout=3,
            serial_number="085125250008",
            product_code="0851",
        ),
        _expected_bus_meter(
            family=MeterFamily.PRO.value,
            name="PRO380 Gateway",
            variant="pro_380",
            slave_id=41,
            transport=TransportType.TCP_GATEWAY,
            host="10.5.2.14",
            port=502,
            timeout=3,
        ),
    ]


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [EDIT_SERIAL_BUS_DYNAMIC_OPTIONS_FIELD_TRANSLATIONS],
)
async def test_serial_bus_options_flow_can_edit_bus_and_meter_addresses(
    hass,
) -> None:
    """The options flow should rename a bus and edit each meter's Modbus ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="085125250008",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    "serial_number": "085125250008",
                    "product_code": "0851",
                },
                {
                    "name": "080125260007",
                    CONF_VARIANT: "grow_800",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "080125260007",
                    "product_code": "0801",
                },
            ],
        },
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "edit_serial_bus"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_serial_bus"

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Main RS485 Bus",
                CONF_SERIAL_PORT: "COM6",
                CONF_BAUDRATE: 19200,
                CONF_BYTESIZE: 8,
                CONF_PARITY: "N",
                CONF_STOPBITS: 1,
                CONF_TIMEOUT: 5,
                CONF_SCAN_INTERVAL: 30,
                "Modbus ID for 085125250008": 5,
                "Modbus ID for 080125260007": 158,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Main RS485 Bus"
    assert entry.data[CONF_SERIAL_PORT] == "COM6"
    assert entry.data[CONF_BAUDRATE] == 19200
    assert entry.data[CONF_PARITY] == "N"
    assert entry.data[CONF_SCAN_INTERVAL] == 30
    assert entry.data[CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="085125250008",
            variant="grow_850",
            slave_id=5,
            serial_port="COM6",
            timeout=5,
            serial_number="085125250008",
            product_code="0851",
            baudrate=19200,
            parity="N",
        ),
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="080125260007",
            variant="grow_800",
            slave_id=158,
            serial_port="COM6",
            timeout=5,
            serial_number="080125260007",
            product_code="0801",
            baudrate=19200,
            parity="N",
        ),
    ]


async def test_serial_bus_manage_routes_action_selects_meter(
    hass,
) -> None:
    """Shared serial-bus entries should allow choosing one meter for route management."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main RS485 Bus",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "085125250008",
                    "product_code": "0851",
                },
                {
                    CONF_FAMILY: MeterFamily.PRO.value,
                    "name": "PRO380 Lab",
                    CONF_VARIANT: "pro_380",
                    CONF_SLAVE_ID: 41,
                },
            ],
        },
        version=4,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "manage_meter_routes"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_meter"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SELECTED_METER: "085125250008"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manage_meter_routes"


async def test_shared_bus_meter_can_add_and_switch_routes(
    hass,
) -> None:
    """Shared serial-bus meters should support their own stored routes and active route."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Titan Modbus Master (COM5)",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    CONF_NAME: "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "075625480002",
                    "product_code": "0756",
                },
                {
                    CONF_FAMILY: MeterFamily.PRO.value,
                    CONF_NAME: "PRO380 Lab",
                    CONF_VARIANT: "pro_380",
                    CONF_SLAVE_ID: 41,
                },
            ],
        },
        version=5,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "manage_meter_routes"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_meter"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SELECTED_METER: "075625480002"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manage_meter_routes"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "add_route"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.BLUETOOTH.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route_purpose"

    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="80:F1:B2:58:DD:5A",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-52,
    )
    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
        return_value=(discovered_meter,),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ONBOARDING},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route_bluetooth_discovered"
    assert result["description_placeholders"] == {
        "count": "1",
        "meter": "075625480002",
    }

    ble_device = SimpleNamespace(name="IM-075625480002", address="80:F1:B2:58:DD:5A")
    validate_gatt = AsyncMock(return_value="075625480002")
    validate_modbus = AsyncMock(return_value=None)
    validate_identity = AsyncMock(return_value=None)
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=validate_gatt,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=validate_modbus,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_DISCOVERED_BLUETOOTH_METER: "075625480002:80:F1:B2:58:DD:5A",
                CONF_SLAVE_ID: 1,
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    grow_meter = next(
        meter
        for meter in entry.data[CONF_METERS]
        if meter.get(CONF_SERIAL_NUMBER) == "075625480002"
    )
    assert len(grow_meter[CONF_ROUTES]) == 2
    assert grow_meter[CONF_ACTIVE_ROUTE] == "serial:COM5:1"

    bluetooth_route = next(
        route
        for route in grow_meter[CONF_ROUTES]
        if route[CONF_TRANSPORT] == TransportType.BLUETOOTH.value
    )
    assert bluetooth_route[CONF_ROUTE_PURPOSE] == ROUTE_PURPOSE_ONBOARDING
    validate_modbus.assert_not_awaited()
    assert (
        validate_identity.call_args.args[0][CONF_BLUETOOTH_PAIRING_MODE]
        == BLUETOOTH_PAIRING_MODE_NEVER
    )
    assert CONF_BLUETOOTH_PAIRING_TIMEOUT not in validate_identity.call_args.args[0]
    assert CONF_BLUETOOTH_FORCE_REPAIR not in validate_identity.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_PIN not in validate_identity.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_MODE not in validate_gatt.call_args.args[0]
    assert CONF_BLUETOOTH_FORCE_REPAIR not in validate_gatt.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_PIN not in validate_gatt.call_args.args[0]
    assert CONF_BLUETOOTH_PAIRING_MODE not in bluetooth_route
    assert CONF_BLUETOOTH_FORCE_REPAIR not in bluetooth_route
    assert CONF_BLUETOOTH_PAIRING_PIN not in bluetooth_route
    bluetooth_route_key = "bluetooth:80:F1:B2:58:DD:5A:1"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "manage_meter_routes"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SELECTED_METER: "075625480002"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "switch_route"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "switch_route"

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SELECTED_ROUTE: bluetooth_route_key},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    grow_meter = next(
        meter
        for meter in entry.data[CONF_METERS]
        if meter.get(CONF_SERIAL_NUMBER) == "075625480002"
    )
    assert grow_meter[CONF_ACTIVE_ROUTE].startswith("bluetooth:")


async def test_tcp_options_flow_can_edit_host_port_and_modbus_address(
    hass,
) -> None:
    """The options flow should update TCP route details without changing identity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "update_connection"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "update_connection"

    validate_mock = AsyncMock(return_value=None)
    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=validate_mock,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.68.85",
                CONF_PORT: 1502,
                CONF_SLAVE_ID: 2,
                CONF_TIMEOUT: 4,
                CONF_SCAN_INTERVAL: 20,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "075625480002"
    assert entry.data[CONF_HOST] == "192.168.68.85"
    assert entry.data[CONF_PORT] == 1502
    assert entry.data[CONF_SLAVE_ID] == 2
    assert entry.data[CONF_TIMEOUT] == 4
    assert entry.data[CONF_SCAN_INTERVAL] == 20
    validate_mock.assert_awaited_once()


async def test_bluetooth_options_flow_can_edit_address_name_and_polling(
    hass,
) -> None:
    """The options flow should update Bluetooth route details without changing identity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.BLUETOOTH.value,
            CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_BLUETOOTH_NAME: "IM-075625480002",
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "update_connection"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "update_connection"

    validate_mock = AsyncMock(return_value=None)
    validate_identity = AsyncMock(return_value=None)
    ble_device = SimpleNamespace(
        name="IM-075625480002-NEW",
        address="11:22:33:44:55:66",
    )
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=validate_mock,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66",
                CONF_BLUETOOTH_NAME: "IM-075625480002-NEW",
                CONF_SLAVE_ID: 2,
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
                CONF_SCAN_INTERVAL: 25,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "075625480002"
    assert entry.data[CONF_BLUETOOTH_ADDRESS] == "11:22:33:44:55:66"
    assert entry.data[CONF_BLUETOOTH_NAME] == "IM-075625480002-NEW"
    assert entry.data[CONF_SLAVE_ID] == 2
    assert entry.data[CONF_TIMEOUT] == DEFAULT_BLUETOOTH_TIMEOUT
    assert entry.data[CONF_SCAN_INTERVAL] == 25
    validate_mock.assert_not_awaited()
    validate_identity.assert_awaited_once()


async def test_bluetooth_proxy_options_flow_can_edit_proxy_and_ble_details(
    hass,
) -> None:
    """The options flow should update Windows BLE proxy route details safely."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.BLUETOOTH_PROXY.value,
            CONF_HOST: DEFAULT_BLE_PROXY_HOST,
            CONF_PORT: DEFAULT_BLE_PROXY_PORT,
            CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_BLUETOOTH_NAME: "IM-075625480002",
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "update_connection"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "update_connection"

    validate_mock = AsyncMock(return_value=None)
    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=validate_mock,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 16026,
                CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66",
                CONF_BLUETOOTH_NAME: "IM-075625480002-NEW",
                CONF_SLAVE_ID: 2,
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
                CONF_SCAN_INTERVAL: 25,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_PORT] == 16026
    assert entry.data[CONF_BLUETOOTH_ADDRESS] == "11:22:33:44:55:66"
    assert entry.data[CONF_BLUETOOTH_NAME] == "IM-075625480002-NEW"
    assert entry.data[CONF_SLAVE_ID] == 2
    assert entry.data[CONF_TIMEOUT] == DEFAULT_BLUETOOTH_TIMEOUT
    assert entry.data[CONF_SCAN_INTERVAL] == 25
    validate_mock.assert_awaited_once()


@pytest.mark.usefixtures("real_entry_setup")
async def test_options_submit_preserves_active_route_and_deduplicates_routes(
    hass,
) -> None:
    """Submitting options should preserve the selected route and clean duplicates."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.88",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 3,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                },
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 4,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.88",
                    CONF_PORT: 502,
                },
                {
                    CONF_TRANSPORT: TransportType.TCP_WIFI.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 5,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.76",
                    CONF_PORT: 502,
                },
            ],
            CONF_ACTIVE_ROUTE: "tcp_wifi:192.168.68.88:502:1",
        },
        version=5,
    )
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(),
        async_shutdown=AsyncMock(),
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.build_runtime_coordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"action": "update_polling"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "update_polling"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SCAN_INTERVAL: 20},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_ACTIVE_ROUTE] == "tcp_wifi:192.168.68.88:502:1"
    assert entry.data[CONF_HOST] == "192.168.68.88"
    assert entry.data[CONF_PORT] == 502
    assert entry.data[CONF_SCAN_INTERVAL] == 20
    assert len(entry.data[CONF_ROUTES]) == 2
    route_keys = [build_route_key(route) for route in get_configured_routes(entry.data)]
    assert route_keys == [
        "tcp_wifi:192.168.68.76:502:1",
        "tcp_wifi:192.168.68.88:502:1",
    ]
    first_route = entry.data[CONF_ROUTES][0]
    assert first_route[CONF_HOST] == "192.168.68.76"
    assert first_route[CONF_TIMEOUT] == 5


async def test_options_flow_can_add_onboarding_route_and_switch_active_route(
    hass,
) -> None:
    """Single-meter entries should store extra routes and allow switching the active one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 3,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.80",
                    CONF_PORT: 502,
                }
            ],
            CONF_ACTIVE_ROUTE: "tcp_ethernet:192.168.68.80:502:1",
        },
        version=4,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "add_route"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.BLUETOOTH.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route_purpose"

    discovered_meter = DiscoveredGrowBluetoothMeter(
        address="80:F1:B2:58:DD:5A",
        bluetooth_name="IM-075625480002",
        serial_number="075625480002",
        variant="grow_750",
        model_title="GROW 3P4S",
        product_code="0756",
        rssi=-52,
    )
    with patch(
        "homeassistant.components.inepro_metering.config_flow.async_discover_grow_bluetooth_meters",
        return_value=(discovered_meter,),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ONBOARDING},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route_bluetooth_discovered"
    assert result["description_placeholders"] == {
        "count": "1",
        "meter": "075625480002",
    }

    ble_device = SimpleNamespace(name="IM-075625480002", address="80:F1:B2:58:DD:5A")
    validate_identity = AsyncMock(return_value=None)
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=validate_identity,
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_DISCOVERED_BLUETOOTH_METER: "075625480002:80:F1:B2:58:DD:5A",
                CONF_SLAVE_ID: 1,
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_TRANSPORT] == TransportType.TCP_ETHERNET.value
    assert entry.data[CONF_ACTIVE_ROUTE] == "tcp_ethernet:192.168.68.80:502:1"
    assert len(entry.data[CONF_ROUTES]) == 2

    routes = get_configured_routes(entry.data)
    bluetooth_route = next(
        route for route in routes if route.transport is TransportType.BLUETOOTH
    )
    assert bluetooth_route.purpose == ROUTE_PURPOSE_ONBOARDING
    assert CONF_BLUETOOTH_PAIRING_PIN not in validate_identity.call_args.args[0]
    assert (
        validate_identity.call_args.args[0][CONF_BLUETOOTH_PAIRING_MODE]
        == BLUETOOTH_PAIRING_MODE_NEVER
    )
    assert (
        validate_identity.call_args.args[0][CONF_TRANSPORT]
        == TransportType.BLUETOOTH.value
    )
    assert CONF_ROUTES not in validate_identity.call_args.args[0]
    assert CONF_ACTIVE_ROUTE not in validate_identity.call_args.args[0]
    assert all(
        CONF_BLUETOOTH_PAIRING_PIN not in route for route in entry.data[CONF_ROUTES]
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "switch_route"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "switch_route"

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SELECTED_ROUTE: build_route_key(bluetooth_route)},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_TRANSPORT] == TransportType.BLUETOOTH.value
    assert entry.data[CONF_BLUETOOTH_ADDRESS] == "80:F1:B2:58:DD:5A"
    assert entry.data[CONF_ACTIVE_ROUTE] == build_route_key(bluetooth_route)


async def test_add_serial_route_skips_helper_only_purpose_step(
    hass,
) -> None:
    """Serial routes should skip the helper-only purpose chooser."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 3,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.80",
                    CONF_PORT: 502,
                }
            ],
            CONF_ACTIVE_ROUTE: "tcp_ethernet:192.168.68.80:502:1",
        },
        version=4,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "add_route"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.SERIAL.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_route_connection"


async def test_tcp_options_flow_rejects_connection_update_to_different_meter(
    hass,
) -> None:
    """The options flow must reject route changes that point to another meter."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "update_connection"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "update_connection"

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(side_effect=IneproIdentityError),
        ),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.68.85",
                CONF_PORT: 1502,
                CONF_SLAVE_ID: 2,
                CONF_TIMEOUT: 4,
                CONF_SCAN_INTERVAL: 20,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "update_connection"
    assert result["errors"] == {"base": "invalid_identity"}
    assert entry.data[CONF_HOST] == "192.168.68.80"
    assert entry.data[CONF_PORT] == 502


async def test_reconfigure_flow_can_switch_single_meter_transport(
    hass,
) -> None:
    """Reconfigure should update one single-meter entry in place."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 3,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.80",
                    CONF_PORT: 502,
                }
            ],
            CONF_ACTIVE_ROUTE: "tcp_ethernet:192.168.68.80:502:1",
        },
        version=5,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transport"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.BLUETOOTH.value},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"

    ble_device = SimpleNamespace(
        name="IM-075625480002-NEW", address="11:22:33:44:55:66"
    )
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_bluetooth_gatt_identity",
            new=AsyncMock(return_value="075625480002"),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66",
                CONF_BLUETOOTH_NAME: "IM-075625480002-NEW",
                CONF_TIMEOUT: DEFAULT_BLUETOOTH_TIMEOUT,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "075625480002"
    assert entry.data[CONF_TRANSPORT] == TransportType.BLUETOOTH.value
    assert entry.data[CONF_BLUETOOTH_ADDRESS] == "11:22:33:44:55:66"
    assert entry.data[CONF_BLUETOOTH_NAME] == "IM-075625480002-NEW"
    assert entry.data[CONF_ACTIVE_ROUTE].startswith("bluetooth:")
    assert len(entry.data[CONF_ROUTES]) == 2
    schedule_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_flow_rejects_identity_mismatch(
    hass,
) -> None:
    """Reconfigure must keep the existing physical meter identity stable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_HOST: "192.168.68.80",
            CONF_PORT: 502,
            CONF_TIMEOUT: 3,
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_ROUTES: [
                {
                    CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
                    CONF_SLAVE_ID: 1,
                    CONF_TIMEOUT: 3,
                    CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
                    CONF_HOST: "192.168.68.80",
                    CONF_PORT: 502,
                }
            ],
            CONF_ACTIVE_ROUTE: "tcp_ethernet:192.168.68.80:502:1",
        },
        version=5,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSPORT: TransportType.TCP_ETHERNET.value},
    )

    with (
        patch(
            "homeassistant.components.inepro_metering.config_flow.async_validate_modbus_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.inepro_metering.config_flow._async_validate_entry_identity",
            new=AsyncMock(side_effect=IneproIdentityError),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.68.85",
                CONF_PORT: 1502,
                CONF_TIMEOUT: 4,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["errors"] == {"base": "invalid_identity"}
    assert entry.data[CONF_HOST] == "192.168.68.80"
    assert entry.data[CONF_PORT] == 502


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [EDIT_SERIAL_BUS_DYNAMIC_CONFIG_FIELD_TRANSLATIONS],
)
async def test_reconfigure_flow_can_edit_shared_serial_bus(
    hass,
) -> None:
    """Reconfigure should reuse the shared-bus edit flow for bus entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="085125250008",
        unique_id="COM5",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    CONF_NAME: "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "085125250008",
                    "product_code": "0851",
                },
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    CONF_NAME: "080125260007",
                    CONF_VARIANT: "grow_800",
                    CONF_SLAVE_ID: 157,
                    CONF_SERIAL_NUMBER: "080125260007",
                    "product_code": "0801",
                },
            ],
        },
        version=4,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_serial_bus"

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Main RS485 Bus",
                CONF_SERIAL_PORT: "COM6",
                CONF_BAUDRATE: 19200,
                CONF_BYTESIZE: 8,
                CONF_PARITY: "N",
                CONF_STOPBITS: 1,
                CONF_TIMEOUT: 5,
                CONF_SCAN_INTERVAL: 30,
                "Modbus ID for 085125250008": 5,
                "Modbus ID for 080125260007": 158,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Main RS485 Bus"
    assert entry.version == 5
    assert entry.data[CONF_SERIAL_PORT] == "COM6"
    assert entry.data[CONF_BAUDRATE] == 19200
    assert entry.data[CONF_PARITY] == "N"
    assert entry.data[CONF_SCAN_INTERVAL] == 30
    assert entry.data[CONF_METERS] == [
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="085125250008",
            variant="grow_850",
            slave_id=5,
            serial_port="COM6",
            timeout=5,
            serial_number="085125250008",
            product_code="0851",
            baudrate=19200,
            parity="N",
        ),
        _expected_bus_meter(
            family=MeterFamily.GROW.value,
            name="080125260007",
            variant="grow_800",
            slave_id=158,
            serial_port="COM6",
            timeout=5,
            serial_number="080125260007",
            product_code="0801",
            baudrate=19200,
            parity="N",
        ),
    ]
    schedule_reload.assert_called_once_with(entry.entry_id)
