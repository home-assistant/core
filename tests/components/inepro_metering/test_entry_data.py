"""Tests for config-entry route helpers."""

from homeassistant.components.inepro_metering.const import (
    CONF_ACTIVE_ROUTE,
    CONF_BAUDRATE,
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
    CONF_TRANSPORT,
    CONF_VARIANT,
    ROUTE_PURPOSE_ACTIVE,
    ROUTE_PURPOSE_ONBOARDING,
    TransportType,
)
from homeassistant.components.inepro_metering.entry_data import (
    ConfiguredMeter,
    ConfiguredRoute,
    build_bus_route,
    build_route_key,
    ensure_bus_meter_routes,
    get_active_route_for_meter,
    get_configured_routes,
    get_meter_routes,
    normalize_entry_route_data,
    with_routes_applied,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT


def _serial_bus_entry_data() -> dict[str, object]:
    """Build shared-bus entry data for one serial route."""
    return {
        CONF_TRANSPORT: TransportType.SERIAL.value,
        CONF_TIMEOUT: 3,
        CONF_SERIAL_PORT: "COM5",
        CONF_BAUDRATE: 9600,
        CONF_BYTESIZE: 8,
        CONF_PARITY: "E",
        CONF_STOPBITS: 1,
        CONF_METERS: [],
    }


def test_get_active_route_for_meter_uses_matching_active_route_key() -> None:
    """The saved active-route key should select the matching configured route."""
    serial_route = ConfiguredRoute(
        transport=TransportType.SERIAL,
        slave_id=157,
        timeout=3,
        serial_port="COM5",
        baudrate=9600,
        bytesize=8,
        parity="E",
        stopbits=1,
    )
    gateway_route = ConfiguredRoute(
        transport=TransportType.TCP_GATEWAY,
        slave_id=157,
        timeout=3,
        host="192.0.2.10",
        port=502,
    )
    meter = ConfiguredMeter(
        family="grow",
        name="075625480002",
        variant="grow_750",
        slave_id=157,
        routes=(serial_route, gateway_route),
        active_route=build_route_key(gateway_route),
    )

    assert get_active_route_for_meter(meter) == gateway_route


def test_get_active_route_for_meter_falls_back_to_first_route_when_key_is_stale() -> (
    None
):
    """A stale active-route key should not break route selection."""
    serial_route = ConfiguredRoute(
        transport=TransportType.SERIAL,
        slave_id=157,
        timeout=3,
        serial_port="COM5",
        baudrate=9600,
        bytesize=8,
        parity="E",
        stopbits=1,
    )
    gateway_route = ConfiguredRoute(
        transport=TransportType.TCP_GATEWAY,
        slave_id=157,
        timeout=3,
        host="192.0.2.10",
        port=502,
    )
    meter = ConfiguredMeter(
        family="grow",
        name="075625480002",
        variant="grow_750",
        slave_id=157,
        routes=(serial_route, gateway_route),
        active_route="bluetooth_proxy:missing",
    )

    assert get_active_route_for_meter(meter) == serial_route


def test_get_meter_routes_synthesizes_bus_route_for_legacy_shared_bus_entry() -> None:
    """Legacy shared-bus entries should still expose one effective bus route."""
    meter = ConfiguredMeter(
        family="grow",
        name="075625480002",
        variant="grow_750",
        slave_id=157,
    )

    routes = get_meter_routes(meter, bus_entry_data=_serial_bus_entry_data())

    assert routes == (
        ConfiguredRoute(
            transport=TransportType.SERIAL,
            slave_id=157,
            timeout=3,
            serial_port="COM5",
            baudrate=9600,
            bytesize=8,
            parity="E",
            stopbits=1,
        ),
    )


def test_ensure_bus_meter_routes_adds_missing_bus_route_without_losing_active_route() -> (
    None
):
    """Adding the owning bus route should not replace the saved active route."""
    onboarding_route = ConfiguredRoute(
        transport=TransportType.BLUETOOTH_PROXY,
        slave_id=157,
        timeout=5,
        purpose=ROUTE_PURPOSE_ONBOARDING,
        host="172.28.224.1",
        port=15026,
        bluetooth_address="80:F1:B2:58:DD:5A",
        bluetooth_name="IM-075625480002",
    )
    meter = ConfiguredMeter(
        family="grow",
        name="075625480002",
        variant="grow_750",
        slave_id=157,
        routes=(onboarding_route,),
        active_route=build_route_key(onboarding_route),
    )

    updated_meter = ensure_bus_meter_routes(
        meter,
        bus_entry_data=_serial_bus_entry_data(),
    )

    assert updated_meter.active_route == build_route_key(onboarding_route)
    assert updated_meter.routes[0] == onboarding_route
    assert updated_meter.routes[1] == build_bus_route(
        _serial_bus_entry_data(),
        slave_id=157,
    )


def test_with_routes_applied_mirrors_selected_active_route_to_top_level_fields() -> (
    None
):
    """Persisted route data should mirror the active route back to legacy fields."""
    serial_route = ConfiguredRoute(
        transport=TransportType.SERIAL,
        slave_id=157,
        timeout=3,
        serial_port="COM5",
        baudrate=9600,
        bytesize=8,
        parity="E",
        stopbits=1,
    )
    gateway_route = ConfiguredRoute(
        transport=TransportType.TCP_GATEWAY,
        slave_id=157,
        timeout=5,
        host="192.0.2.10",
        port=502,
    )
    entry_data = {
        CONF_FAMILY: "grow",
        CONF_NAME: "075625480002",
        CONF_VARIANT: "grow_750",
        CONF_SERIAL_NUMBER: "075625480002",
        CONF_TRANSPORT: TransportType.SERIAL.value,
        CONF_SLAVE_ID: 157,
        CONF_TIMEOUT: 3,
        CONF_SERIAL_PORT: "COM5",
        CONF_BAUDRATE: 9600,
        CONF_BYTESIZE: 8,
        CONF_PARITY: "E",
        CONF_STOPBITS: 1,
    }

    updated = with_routes_applied(
        entry_data,
        (serial_route, gateway_route),
        active_route_key=build_route_key(gateway_route),
    )

    assert updated[CONF_TRANSPORT] == TransportType.TCP_GATEWAY.value
    assert updated[CONF_HOST] == "192.0.2.10"
    assert updated[CONF_PORT] == 502
    assert updated[CONF_SLAVE_ID] == 157
    assert updated[CONF_TIMEOUT] == 5
    assert updated[CONF_ACTIVE_ROUTE] == build_route_key(gateway_route)
    assert len(updated[CONF_ROUTES]) == 2


def test_normalize_entry_route_data_collapses_duplicate_route_keys() -> None:
    """Persisted duplicate routes should collapse without losing the active route."""
    advertised_route = ConfiguredRoute(
        transport=TransportType.TCP_GATEWAY,
        slave_id=157,
        timeout=3,
        host="192.0.2.10",
        port=502,
    )
    duplicate_route = ConfiguredRoute(
        transport=TransportType.TCP_GATEWAY,
        slave_id=157,
        timeout=5,
        host="192.0.2.10",
        port=502,
    )
    active_route = ConfiguredRoute(
        transport=TransportType.TCP_GATEWAY,
        slave_id=157,
        timeout=4,
        host="192.0.2.20",
        port=502,
    )
    entry_data = with_routes_applied(
        {
            CONF_FAMILY: "grow",
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SLAVE_ID: 157,
            CONF_TIMEOUT: 3,
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 502,
        },
        (advertised_route, active_route),
        active_route_key=build_route_key(active_route),
    )
    entry_data[CONF_ROUTES].append(
        {
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SLAVE_ID: 157,
            CONF_TIMEOUT: 5,
            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 502,
        }
    )

    updated = normalize_entry_route_data(entry_data)

    assert updated[CONF_HOST] == "192.0.2.20"
    assert updated[CONF_ACTIVE_ROUTE] == build_route_key(active_route)
    assert len(updated[CONF_ROUTES]) == 2
    deduped_route = next(
        route for route in updated[CONF_ROUTES] if route[CONF_HOST] == "192.0.2.10"
    )
    assert deduped_route[CONF_TIMEOUT] == duplicate_route.timeout


def test_normalize_entry_route_data_collapses_direct_tcp_endpoint_conflict() -> None:
    """Direct TCP Wi-Fi/Ethernet labels should not duplicate one endpoint."""
    wifi_route = ConfiguredRoute(
        transport=TransportType.TCP_WIFI,
        slave_id=1,
        timeout=3,
        host="192.168.68.76",
        port=502,
    )
    ethernet_route = ConfiguredRoute(
        transport=TransportType.TCP_ETHERNET,
        slave_id=1,
        timeout=5,
        host="192.168.68.76",
        port=502,
    )
    entry_data = with_routes_applied(
        {
            CONF_FAMILY: "grow",
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 3,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
        },
        (wifi_route,),
        active_route_key=build_route_key(wifi_route),
    )
    entry_data[CONF_ROUTES].append(
        {
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 5,
            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
        }
    )

    updated = normalize_entry_route_data(entry_data)

    assert updated[CONF_TRANSPORT] == TransportType.TCP_ETHERNET.value
    assert updated[CONF_HOST] == "192.168.68.76"
    assert updated[CONF_PORT] == 502
    assert updated[CONF_ACTIVE_ROUTE] == build_route_key(ethernet_route)
    assert [build_route_key(route) for route in get_configured_routes(updated)] == [
        build_route_key(ethernet_route)
    ]


def test_normalize_entry_route_data_keeps_active_alternate_direct_tcp_route() -> None:
    """Collapsing another endpoint conflict should not change the active route."""
    stale_wifi_route = ConfiguredRoute(
        transport=TransportType.TCP_WIFI,
        slave_id=1,
        timeout=3,
        host="192.168.68.76",
        port=502,
    )
    active_wifi_route = ConfiguredRoute(
        transport=TransportType.TCP_WIFI,
        slave_id=1,
        timeout=3,
        host="192.168.68.88",
        port=502,
    )
    ethernet_route = ConfiguredRoute(
        transport=TransportType.TCP_ETHERNET,
        slave_id=1,
        timeout=5,
        host="192.168.68.76",
        port=502,
    )
    entry_data = with_routes_applied(
        {
            CONF_FAMILY: "grow",
            CONF_NAME: "075625480002",
            CONF_VARIANT: "grow_750",
            CONF_SERIAL_NUMBER: "075625480002",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 3,
            CONF_HOST: "192.168.68.88",
            CONF_PORT: 502,
        },
        (stale_wifi_route, active_wifi_route),
        active_route_key=build_route_key(active_wifi_route),
    )
    entry_data[CONF_ROUTES].append(
        {
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 5,
            CONF_ROUTE_PURPOSE: ROUTE_PURPOSE_ACTIVE,
            CONF_HOST: "192.168.68.76",
            CONF_PORT: 502,
        }
    )

    updated = normalize_entry_route_data(entry_data)

    assert updated[CONF_TRANSPORT] == TransportType.TCP_WIFI.value
    assert updated[CONF_HOST] == "192.168.68.88"
    assert updated[CONF_PORT] == 502
    assert updated[CONF_ACTIVE_ROUTE] == build_route_key(active_wifi_route)
    assert [build_route_key(route) for route in get_configured_routes(updated)] == [
        build_route_key(ethernet_route),
        build_route_key(active_wifi_route),
    ]
