"""Helpers for config-entry data shapes used by Inepro Metering."""

from dataclasses import dataclass, replace
from typing import Any

from inepro_metering.routes import (
    MeterRouteDefinition,
    RouteEndpoint,
    build_route_key,
    route_matches_endpoint,
)

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT

from .const import (
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
    CONF_TRANSPORT,
    CONF_VARIANT,
    ROUTE_PURPOSE_ACTIVE,
    TransportType,
)
from .discovery import parse_grow_serial_number
from .models import get_profile_for_variant


@dataclass(frozen=True, slots=True)
class ConfiguredMeter:
    """One configured Inepro meter inside a config entry."""

    family: str
    name: str
    variant: str
    slave_id: int
    serial_number: str | None = None
    product_code: str | None = None
    routes: tuple[ConfiguredRoute, ...] = ()
    active_route: str | None = None


ConfiguredRoute = MeterRouteDefinition


BUS_TRANSPORTS = {
    TransportType.SERIAL,
    TransportType.TCP_GATEWAY,
}

DIRECT_TCP_TRANSPORTS = {
    TransportType.TCP_ETHERNET,
    TransportType.TCP_WIFI,
}

DIRECT_BLUETOOTH_TRANSPORTS = {
    TransportType.BLUETOOTH,
}

DirectTcpEndpointKey = tuple[str, int, int]
RouteDeduplicationKey = tuple[str, ...]


def is_bus_entry(data: dict[str, Any]) -> bool:
    """Return whether the config entry represents a shared Modbus bus container."""
    return TransportType(data[CONF_TRANSPORT]) in BUS_TRANSPORTS and CONF_METERS in data


def is_serial_bus_entry(data: dict[str, Any]) -> bool:
    """Return whether the config entry represents a serial bus container."""
    return (
        is_bus_entry(data)
        and TransportType(data[CONF_TRANSPORT]) is TransportType.SERIAL
    )


def get_configured_meters(
    data: dict[str, Any], *, title: str
) -> tuple[ConfiguredMeter, ...]:
    """Return configured meters for both new bus and legacy single-meter entries."""
    if is_bus_entry(data):
        return tuple(
            _configured_meter_from_mapping(meter_data)
            for meter_data in data[CONF_METERS]
        )

    serial_number, product_code = _configured_single_entry_identity(data, title=title)
    return (
        ConfiguredMeter(
            family=str(data[CONF_FAMILY]),
            name=title,
            variant=str(data[CONF_VARIANT]),
            slave_id=int(data[CONF_SLAVE_ID]),
            serial_number=serial_number,
            product_code=product_code,
        ),
    )


def serialize_configured_meter(meter: ConfiguredMeter) -> dict[str, Any]:
    """Serialize one configured meter into entry data."""
    data: dict[str, Any] = {
        CONF_FAMILY: meter.family,
        CONF_NAME: meter.name,
        CONF_VARIANT: meter.variant,
        CONF_SLAVE_ID: meter.slave_id,
    }
    if meter.serial_number is not None:
        data[CONF_SERIAL_NUMBER] = meter.serial_number
    if meter.product_code is not None:
        data["product_code"] = meter.product_code
    if meter.routes:
        data[CONF_ROUTES] = [
            serialize_configured_route(route) for route in meter.routes
        ]
    if meter.active_route is not None:
        data[CONF_ACTIVE_ROUTE] = meter.active_route
    return data


def build_bus_unique_id(data: dict[str, Any]) -> str:
    """Build a stable unique ID for one configured bus endpoint."""
    transport = TransportType(data[CONF_TRANSPORT])
    if transport is TransportType.SERIAL:
        endpoint = str(data[CONF_SERIAL_PORT]).strip().upper()
    elif transport is TransportType.BLUETOOTH:
        endpoint = str(data[CONF_BLUETOOTH_ADDRESS]).strip().upper()
    else:
        endpoint = f"{str(data[CONF_HOST]).strip().lower()}:{int(data[CONF_PORT])}"
    return endpoint


def build_meter_key(meter: ConfiguredMeter) -> str:
    """Build a stable per-meter key inside one config entry."""
    if meter.serial_number:
        return meter.serial_number
    return f"{meter.family}:{meter.variant}:{meter.slave_id}"


def get_configured_routes(data: dict[str, Any]) -> tuple[ConfiguredRoute, ...]:
    """Return configured routes for one single-meter entry."""
    if is_bus_entry(data):
        return ()

    if CONF_ROUTES not in data:
        return (_configured_route_from_legacy_entry(data),)

    return deduplicate_configured_routes(
        tuple(
            _configured_route_from_mapping(route_data)
            for route_data in data[CONF_ROUTES]
        )
    )


def deduplicate_configured_routes(
    routes: tuple[ConfiguredRoute, ...],
) -> tuple[ConfiguredRoute, ...]:
    """Return routes with duplicate route identities collapsed in first-seen order.

    Exact duplicate route keys collapse normally. Direct TCP Wi-Fi/Ethernet
    routes also collapse by host/port/slave because mDNS cannot identify which
    physical interface advertised the endpoint. If duplicates exist, the last
    route value wins while the original key order is preserved.
    """
    route_by_key: dict[RouteDeduplicationKey, ConfiguredRoute] = {}
    route_keys: list[RouteDeduplicationKey] = []
    for route in routes:
        route_key = _route_deduplication_key(route)
        if route_key not in route_by_key:
            route_keys.append(route_key)
        route_by_key[route_key] = route
    return tuple(route_by_key[route_key] for route_key in route_keys)


def _route_deduplication_key(route: ConfiguredRoute) -> RouteDeduplicationKey:
    """Return the storage identity used when collapsing duplicate routes."""
    direct_tcp_key = _direct_tcp_endpoint_key(route)
    if direct_tcp_key is not None:
        host, port, slave_id = direct_tcp_key
        return ("direct_tcp", host, str(port), str(slave_id))
    return ("route", build_route_key(route))


def _select_active_route(
    routes: tuple[ConfiguredRoute, ...],
    *,
    active_route_key: str | None,
) -> ConfiguredRoute:
    """Return the active route, allowing direct TCP labels to be corrected."""
    active_route = routes[0]
    if active_route_key is None:
        return active_route

    active_direct_tcp_key = _direct_tcp_endpoint_key_from_route_key(active_route_key)
    matching_direct_tcp_route: ConfiguredRoute | None = None
    for route in routes:
        if build_route_key(route) == active_route_key:
            return route
        if (
            active_direct_tcp_key is not None
            and matching_direct_tcp_route is None
            and _direct_tcp_endpoint_key(route) == active_direct_tcp_key
        ):
            matching_direct_tcp_route = route

    return matching_direct_tcp_route or active_route


def _direct_tcp_endpoint_key(route: ConfiguredRoute) -> DirectTcpEndpointKey | None:
    """Return direct TCP endpoint identity shared by Wi-Fi and Ethernet routes."""
    if route.transport not in DIRECT_TCP_TRANSPORTS:
        return None
    if route.host is None or route.port is None:
        return None
    return (str(route.host).strip().lower(), int(route.port), int(route.slave_id))


def _direct_tcp_endpoint_key_from_route_key(
    route_key: str,
) -> DirectTcpEndpointKey | None:
    """Parse direct TCP endpoint identity from a persisted active-route key."""
    for transport in DIRECT_TCP_TRANSPORTS:
        prefix = f"{transport.value}:"
        if not route_key.startswith(prefix):
            continue

        try:
            host, port, slave_id = route_key[len(prefix) :].rsplit(":", 2)
        except ValueError:
            return None

        try:
            return (host.strip().lower(), int(port), int(slave_id))
        except ValueError:
            return None

    return None


def build_bus_route(
    bus_entry_data: dict[str, Any],
    *,
    slave_id: int,
    purpose: str = ROUTE_PURPOSE_ACTIVE,
) -> ConfiguredRoute:
    """Build the canonical bus route for one shared-bus meter."""
    transport = TransportType(bus_entry_data[CONF_TRANSPORT])
    if transport is TransportType.SERIAL:
        return ConfiguredRoute(
            transport=TransportType.SERIAL,
            slave_id=int(slave_id),
            timeout=int(bus_entry_data[CONF_TIMEOUT]),
            purpose=purpose,
            serial_port=str(bus_entry_data[CONF_SERIAL_PORT]),
            baudrate=int(bus_entry_data[CONF_BAUDRATE]),
            bytesize=int(bus_entry_data[CONF_BYTESIZE]),
            parity=str(bus_entry_data[CONF_PARITY]),
            stopbits=int(bus_entry_data[CONF_STOPBITS]),
        )

    if transport is TransportType.TCP_GATEWAY:
        return ConfiguredRoute(
            transport=TransportType.TCP_GATEWAY,
            slave_id=int(slave_id),
            timeout=int(bus_entry_data[CONF_TIMEOUT]),
            purpose=purpose,
            host=str(bus_entry_data[CONF_HOST]),
            port=int(bus_entry_data[CONF_PORT]),
        )

    raise ValueError(f"Unsupported shared-bus transport: {transport.value}")


def build_serial_bus_route(
    bus_entry_data: dict[str, Any],
    *,
    slave_id: int,
    purpose: str = ROUTE_PURPOSE_ACTIVE,
) -> ConfiguredRoute:
    """Build the canonical serial-bus route for one shared-bus meter."""
    return build_bus_route(bus_entry_data, slave_id=slave_id, purpose=purpose)


def get_meter_routes(
    meter: ConfiguredMeter,
    *,
    bus_entry_data: dict[str, Any] | None = None,
) -> tuple[ConfiguredRoute, ...]:
    """Return stored routes for one meter, synthesizing legacy bus routes when needed."""
    if meter.routes:
        return deduplicate_configured_routes(meter.routes)

    if bus_entry_data is not None and is_bus_entry(bus_entry_data):
        # Older shared-bus entries stored connection details only at the bus
        # level, so synthesize the owning bus route for helper callers.
        return (build_bus_route(bus_entry_data, slave_id=meter.slave_id),)

    return ()


def get_active_route_for_meter(
    meter: ConfiguredMeter,
    *,
    bus_entry_data: dict[str, Any] | None = None,
) -> ConfiguredRoute:
    """Return the currently active route for one configured meter.

    If the stored active-route key no longer matches any saved route, fall back
    to the first configured route to preserve upgrade compatibility.
    """
    routes = get_meter_routes(meter, bus_entry_data=bus_entry_data)
    if not routes:
        raise ValueError("At least one route is required for a configured meter")

    if meter.active_route is not None:
        return _select_active_route(
            routes,
            active_route_key=meter.active_route,
        )

    return routes[0]


def route_matches_connection(
    route: ConfiguredRoute,
    connection_data: dict[str, Any],
) -> bool:
    """Return whether a route targets the same transport endpoint as connection data."""
    return route_matches_endpoint(
        route,
        RouteEndpoint(
            transport=TransportType(connection_data[CONF_TRANSPORT]),
            host=(
                None
                if connection_data.get(CONF_HOST) is None
                else str(connection_data[CONF_HOST])
            ),
            port=(
                None
                if connection_data.get(CONF_PORT) is None
                else int(connection_data[CONF_PORT])
            ),
            serial_port=(
                None
                if connection_data.get(CONF_SERIAL_PORT) is None
                else str(connection_data[CONF_SERIAL_PORT])
            ),
            baudrate=(
                None
                if connection_data.get(CONF_BAUDRATE) is None
                else int(connection_data[CONF_BAUDRATE])
            ),
            bytesize=(
                None
                if connection_data.get(CONF_BYTESIZE) is None
                else int(connection_data[CONF_BYTESIZE])
            ),
            parity=(
                None
                if connection_data.get(CONF_PARITY) is None
                else str(connection_data[CONF_PARITY])
            ),
            stopbits=(
                None
                if connection_data.get(CONF_STOPBITS) is None
                else int(connection_data[CONF_STOPBITS])
            ),
            bluetooth_address=(
                None
                if connection_data.get(CONF_BLUETOOTH_ADDRESS) is None
                else str(connection_data[CONF_BLUETOOTH_ADDRESS])
            ),
            bluetooth_name=(
                None
                if connection_data.get(CONF_BLUETOOTH_NAME) is None
                else str(connection_data[CONF_BLUETOOTH_NAME])
            ),
        ),
    )


def get_bus_route_for_meter(
    meter: ConfiguredMeter,
    *,
    bus_entry_data: dict[str, Any],
) -> ConfiguredRoute:
    """Return the saved route that points back to the owning shared bus."""
    routes = get_meter_routes(meter, bus_entry_data=bus_entry_data)
    for route in routes:
        if route_matches_connection(route, bus_entry_data):
            return route
    return build_bus_route(bus_entry_data, slave_id=meter.slave_id)


def get_serial_bus_route_for_meter(
    meter: ConfiguredMeter,
    *,
    bus_entry_data: dict[str, Any],
) -> ConfiguredRoute:
    """Return the saved route that points back to the owning serial bus."""
    return get_bus_route_for_meter(meter, bus_entry_data=bus_entry_data)


def with_meter_routes(
    meter: ConfiguredMeter,
    routes: tuple[ConfiguredRoute, ...],
    *,
    active_route_key: str | None = None,
) -> ConfiguredMeter:
    """Return one configured meter with updated routes and active-route metadata."""
    routes = deduplicate_configured_routes(routes)
    if not routes:
        raise ValueError("At least one route is required for a configured meter")

    active_route = _select_active_route(routes, active_route_key=active_route_key)

    return ConfiguredMeter(
        family=meter.family,
        name=meter.name,
        variant=meter.variant,
        slave_id=active_route.slave_id,
        serial_number=meter.serial_number,
        product_code=meter.product_code,
        routes=routes,
        active_route=build_route_key(active_route),
    )


def ensure_bus_meter_routes(
    meter: ConfiguredMeter,
    *,
    bus_entry_data: dict[str, Any],
) -> ConfiguredMeter:
    """Ensure one shared-bus meter has at least one saved route back to the bus."""
    routes = list(get_meter_routes(meter, bus_entry_data=bus_entry_data))
    # Preserve any onboarding or alternate routes, but always persist a route
    # that points back to the owning shared bus so runtime reloads stay stable.
    if not any(route_matches_connection(route, bus_entry_data) for route in routes):
        routes.append(build_bus_route(bus_entry_data, slave_id=meter.slave_id))

    active_route_key = meter.active_route
    if active_route_key is None and routes:
        active_route_key = build_route_key(routes[0])

    return with_meter_routes(meter, tuple(routes), active_route_key=active_route_key)


def ensure_serial_bus_meter_routes(
    meter: ConfiguredMeter,
    *,
    bus_entry_data: dict[str, Any],
) -> ConfiguredMeter:
    """Ensure one shared-bus meter has at least one saved route back to the bus."""
    return ensure_bus_meter_routes(meter, bus_entry_data=bus_entry_data)


def serialize_configured_route(route: ConfiguredRoute) -> dict[str, Any]:
    """Serialize one configured route into entry data."""
    data: dict[str, Any] = {
        CONF_TRANSPORT: route.transport.value,
        CONF_SLAVE_ID: route.slave_id,
        CONF_TIMEOUT: route.timeout,
        CONF_ROUTE_PURPOSE: route.purpose,
    }
    if route.host is not None:
        data[CONF_HOST] = route.host
    if route.port is not None:
        data[CONF_PORT] = route.port
    if route.serial_port is not None:
        data[CONF_SERIAL_PORT] = route.serial_port
    if route.baudrate is not None:
        data[CONF_BAUDRATE] = route.baudrate
    if route.bytesize is not None:
        data[CONF_BYTESIZE] = route.bytesize
    if route.parity is not None:
        data[CONF_PARITY] = route.parity
    if route.stopbits is not None:
        data[CONF_STOPBITS] = route.stopbits
    if route.bluetooth_address is not None:
        data[CONF_BLUETOOTH_ADDRESS] = route.bluetooth_address
    if route.bluetooth_name is not None:
        data[CONF_BLUETOOTH_NAME] = route.bluetooth_name
    return data


def get_active_route(data: dict[str, Any]) -> ConfiguredRoute:
    """Return the currently active route for one single-meter entry."""
    routes = get_configured_routes(data)
    active_route_key = data.get(CONF_ACTIVE_ROUTE)
    if isinstance(active_route_key, str):
        return _select_active_route(routes, active_route_key=active_route_key)
    return routes[0]


def build_route_from_entry_data(
    entry_data: dict[str, Any],
    *,
    purpose: str = ROUTE_PURPOSE_ACTIVE,
) -> ConfiguredRoute:
    """Build one configured route from top-level entry connection data."""
    route = _configured_route_from_mapping(entry_data)
    return ConfiguredRoute(
        transport=route.transport,
        slave_id=route.slave_id,
        timeout=route.timeout,
        purpose=purpose,
        host=route.host,
        port=route.port,
        serial_port=route.serial_port,
        baudrate=route.baudrate,
        bytesize=route.bytesize,
        parity=route.parity,
        stopbits=route.stopbits,
        bluetooth_address=route.bluetooth_address,
        bluetooth_name=route.bluetooth_name,
    )


def with_routes_applied(
    entry_data: dict[str, Any],
    routes: tuple[ConfiguredRoute, ...],
    *,
    active_route_key: str | None = None,
) -> dict[str, Any]:
    """Return entry data with routes stored and the active route mirrored top-level."""
    routes = deduplicate_configured_routes(routes)
    if not routes:
        raise ValueError("At least one route is required")

    serialized_routes = [serialize_configured_route(route) for route in routes]
    active_route = _select_active_route(routes, active_route_key=active_route_key)

    new_data = {
        key: value
        for key, value in entry_data.items()
        if key
        not in {
            CONF_HOST,
            CONF_PORT,
            CONF_SERIAL_PORT,
            CONF_BAUDRATE,
            CONF_BYTESIZE,
            CONF_PARITY,
            CONF_STOPBITS,
            CONF_BLUETOOTH_ADDRESS,
            CONF_BLUETOOTH_NAME,
            CONF_SLAVE_ID,
            CONF_TIMEOUT,
            CONF_TRANSPORT,
            CONF_ROUTES,
            CONF_ACTIVE_ROUTE,
        }
    }
    new_data.update(serialize_configured_route(active_route))
    new_data[CONF_ROUTES] = serialized_routes
    new_data[CONF_ACTIVE_ROUTE] = build_route_key(active_route)
    return new_data


def normalize_entry_route_data(
    entry_data: dict[str, Any],
    *,
    title: str = "",
) -> dict[str, Any]:
    """Return entry data with duplicate routes removed and active route mirrored."""
    if is_bus_entry(entry_data):
        normalized_meters: list[dict[str, Any]] = []
        changed = False
        for meter in get_configured_meters(entry_data, title=title):
            routes = deduplicate_configured_routes(meter.routes)
            if routes:
                normalized_meter = with_meter_routes(
                    meter,
                    routes,
                    active_route_key=meter.active_route,
                )
            else:
                normalized_meter = meter
            changed = changed or normalized_meter != meter
            normalized_meters.append(serialize_configured_meter(normalized_meter))
        if not changed:
            return entry_data
        return {
            **entry_data,
            CONF_METERS: normalized_meters,
        }

    if CONF_ROUTES not in entry_data:
        return entry_data

    active_route_key = entry_data.get(CONF_ACTIVE_ROUTE)
    routes = get_configured_routes(entry_data)
    if not routes:
        return entry_data
    return with_routes_applied(
        entry_data,
        routes,
        active_route_key=active_route_key
        if isinstance(active_route_key, str)
        else None,
    )


def update_single_meter_tcp_route_from_zeroconf(
    entry_data: dict[str, Any],
    *,
    host: str,
    port: int,
) -> dict[str, Any]:
    """Return single-meter entry data refreshed from a Zeroconf TCP endpoint."""
    new_data = dict(entry_data)
    if is_bus_entry(entry_data):
        return new_data

    try:
        entry_transport = TransportType(entry_data[CONF_TRANSPORT])
    except KeyError, ValueError:
        return new_data

    if entry_transport not in DIRECT_TCP_TRANSPORTS:
        return new_data

    route_data_list = entry_data.get(CONF_ROUTES)
    if not isinstance(route_data_list, list):
        if CONF_HOST in new_data:
            new_data[CONF_HOST] = host
        if CONF_PORT in new_data:
            new_data[CONF_PORT] = port
        return new_data

    active_route_key = entry_data.get(CONF_ACTIVE_ROUTE)
    routes = list(get_configured_routes(entry_data))
    direct_route_indexes: list[int] = []
    target_indexes: set[int] = set()

    for index, route in enumerate(routes):
        if route.transport not in DIRECT_TCP_TRANSPORTS:
            continue

        direct_route_indexes.append(index)
        if (
            route.transport is entry_transport
            and route.host == host
            and route.port == port
        ):
            target_indexes.add(index)

    if not target_indexes and len(direct_route_indexes) == 1:
        target_indexes.add(direct_route_indexes[0])

    for index in target_indexes:
        route = routes[index]
        updated_route = replace(route, host=host, port=port)
        routes[index] = updated_route
        if build_route_key(route) == active_route_key:
            active_route_key = build_route_key(updated_route)

    if not target_indexes:
        route_template = (
            routes[direct_route_indexes[0]]
            if direct_route_indexes
            else build_route_from_entry_data(
                {
                    **entry_data,
                    CONF_TRANSPORT: entry_transport.value,
                    CONF_HOST: host,
                    CONF_PORT: port,
                }
            )
        )
        routes.append(
            replace(
                route_template,
                transport=entry_transport,
                host=host,
                port=port,
            )
        )

    return with_routes_applied(
        entry_data,
        tuple(routes),
        active_route_key=active_route_key
        if isinstance(active_route_key, str)
        else None,
    )


def update_single_meter_bluetooth_route_from_discovery(
    entry_data: dict[str, Any],
    *,
    address: str,
    bluetooth_name: str,
) -> dict[str, Any]:
    """Return single-meter entry data refreshed from a Bluetooth discovery."""
    new_data = dict(entry_data)
    if is_bus_entry(entry_data):
        return new_data

    try:
        entry_transport = TransportType(entry_data[CONF_TRANSPORT])
    except KeyError, ValueError:
        return new_data

    if entry_transport not in DIRECT_BLUETOOTH_TRANSPORTS:
        return new_data

    original_address = str(entry_data.get(CONF_BLUETOOTH_ADDRESS, "")).strip().upper()
    if CONF_BLUETOOTH_ADDRESS in new_data:
        new_data[CONF_BLUETOOTH_ADDRESS] = address
    if CONF_BLUETOOTH_NAME in new_data or bluetooth_name:
        new_data[CONF_BLUETOOTH_NAME] = bluetooth_name

    route_data_list = entry_data.get(CONF_ROUTES)
    if not isinstance(route_data_list, list):
        return new_data

    active_route_key = entry_data.get(CONF_ACTIVE_ROUTE)
    route_updates: list[dict[str, Any]] = []
    bluetooth_route_indexes: list[int] = []
    target_indexes: set[int] = set()
    active_route_updated = False
    active_route_replacement: ConfiguredRoute | None = None

    for index, route_data in enumerate(route_data_list):
        route = _configured_route_from_mapping(route_data)
        serialized_route = dict(route_data)
        route_updates.append(serialized_route)
        if route.transport is not TransportType.BLUETOOTH:
            continue

        bluetooth_route_indexes.append(index)
        route_key = build_route_key(route)
        if route_key == active_route_key:
            target_indexes.add(index)
        if str(route.bluetooth_address or "").strip().upper() == original_address:
            target_indexes.add(index)

    if not target_indexes and len(bluetooth_route_indexes) == 1:
        target_indexes.add(bluetooth_route_indexes[0])

    for index in target_indexes:
        route = _configured_route_from_mapping(route_updates[index])
        updated_route = replace(
            route,
            bluetooth_address=address,
            bluetooth_name=bluetooth_name,
        )
        route_updates[index] = serialize_configured_route(updated_route)
        if build_route_key(route) == active_route_key:
            active_route_updated = True
            active_route_replacement = updated_route

    new_data[CONF_ROUTES] = route_updates
    if active_route_updated and active_route_replacement is not None:
        new_data[CONF_ACTIVE_ROUTE] = build_route_key(active_route_replacement)
    return new_data


def _configured_single_entry_identity(
    data: dict[str, Any],
    *,
    title: str,
) -> tuple[str | None, str | None]:
    """Return the stored serial and product code for one single-meter entry."""
    serial_number = data.get(CONF_SERIAL_NUMBER)
    normalized_serial = serial_number.strip() if isinstance(serial_number, str) else ""
    parsed_serial = (
        parse_grow_serial_number(normalized_serial) if normalized_serial else None
    )

    if parsed_serial is None:
        for candidate in (data.get(CONF_NAME), title):
            if not isinstance(candidate, str):
                continue
            parsed_serial = parse_grow_serial_number(candidate.strip())
            if parsed_serial is not None:
                if not normalized_serial:
                    normalized_serial = parsed_serial.serial_number
                break

    product_code = None if parsed_serial is None else parsed_serial.product_code
    return (normalized_serial or None, product_code)


def _configured_meter_from_mapping(data: dict[str, Any]) -> ConfiguredMeter:
    """Normalize one serialized meter mapping."""
    configured_name = str(data[CONF_NAME])
    parsed_serial = parse_grow_serial_number(configured_name)
    serial_number = data.get(CONF_SERIAL_NUMBER)
    product_code = data.get("product_code")
    family = data.get(CONF_FAMILY)

    if serial_number is None and parsed_serial is not None:
        serial_number = parsed_serial.serial_number
    if product_code is None and parsed_serial is not None:
        product_code = parsed_serial.product_code
    if family is None:
        family = get_profile_for_variant(str(data[CONF_VARIANT])).family.value

    return ConfiguredMeter(
        family=str(family),
        name=configured_name,
        variant=str(data[CONF_VARIANT]),
        slave_id=int(data[CONF_SLAVE_ID]),
        serial_number=serial_number,
        product_code=product_code,
        routes=tuple(
            _configured_route_from_mapping(route_data)
            for route_data in data.get(CONF_ROUTES, ())
        ),
        active_route=(
            None
            if data.get(CONF_ACTIVE_ROUTE) is None
            else str(data[CONF_ACTIVE_ROUTE])
        ),
    )


def _configured_route_from_legacy_entry(data: dict[str, Any]) -> ConfiguredRoute:
    """Build one configured route from legacy top-level connection fields."""
    return _configured_route_from_mapping(data)


def _configured_route_from_mapping(data: dict[str, Any]) -> ConfiguredRoute:
    """Normalize one serialized route mapping."""
    return ConfiguredRoute(
        transport=TransportType(data[CONF_TRANSPORT]),
        slave_id=int(data[CONF_SLAVE_ID]),
        timeout=int(data[CONF_TIMEOUT]),
        purpose=str(data.get(CONF_ROUTE_PURPOSE, ROUTE_PURPOSE_ACTIVE)),
        host=data.get(CONF_HOST),
        port=None if data.get(CONF_PORT) is None else int(data[CONF_PORT]),
        serial_port=data.get(CONF_SERIAL_PORT),
        baudrate=None if data.get(CONF_BAUDRATE) is None else int(data[CONF_BAUDRATE]),
        bytesize=None if data.get(CONF_BYTESIZE) is None else int(data[CONF_BYTESIZE]),
        parity=data.get(CONF_PARITY),
        stopbits=None if data.get(CONF_STOPBITS) is None else int(data[CONF_STOPBITS]),
        bluetooth_address=data.get(CONF_BLUETOOTH_ADDRESS),
        bluetooth_name=data.get(CONF_BLUETOOTH_NAME),
    )
