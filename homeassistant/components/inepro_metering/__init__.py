"""The Inepro Metering integration."""

from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_ACTIVE_ROUTE,
    CONF_FAMILY,
    CONF_METERS,
    CONF_ROUTES,
    CONF_SERIAL_NUMBER,
    CONF_SLAVE_ID,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DOMAIN,
    TransportType,
)
from .coordinator import (
    IneproMeteringCoordinator,
    IneproSerialBusCoordinator,
    build_runtime_coordinator,
)
from .device_identity import (
    configured_meter_device_identifier,
    gateway_device_identifier,
    meter_device_identifier,
)
from .discovery import parse_grow_serial_number
from .entry_data import (
    ConfiguredMeter,
    build_meter_key,
    build_route_from_entry_data,
    ensure_bus_meter_routes,
    get_configured_meters,
    is_bus_entry,
    serialize_configured_meter,
    with_routes_applied,
)
from .gateway_support import entry_supports_gateway_management, gateway_display_name
from .modbus import IneproMeteringError
from .models import get_profile

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.TEXT,
    Platform.BUTTON,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CONF_APPLY = "apply"
CONF_PASSWORD = "password"
CONF_SSID = "ssid"

SERVICE_SET_WIFI_CREDENTIALS = "set_wifi_credentials"

EXC_WIFI_CREDENTIALS_INVALID = "wifi_credentials_invalid"
EXC_WIFI_CREDENTIALS_METER_NOT_FOUND = "wifi_credentials_meter_not_found"
EXC_WIFI_CREDENTIALS_NOT_LOADED = "wifi_credentials_not_loaded"
EXC_WIFI_CREDENTIALS_UNSUPPORTED = "wifi_credentials_unsupported"
EXC_WIFI_CREDENTIALS_WRITE_FAILED = "wifi_credentials_write_failed"

SET_WIFI_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_NUMBER): cv.string,
        vol.Required(CONF_SSID): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_APPLY, default=True): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Inepro Metering domain."""
    _async_register_services(hass)
    return True


@dataclass(frozen=True, slots=True)
class _WiFiServiceTarget:
    """A configured meter and the live coordinator route that can write to it."""

    coordinator: IneproMeteringCoordinator | IneproSerialBusCoordinator
    meter: ConfiguredMeter


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Inepro Metering from a config entry."""
    coordinator = build_runtime_coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    _async_update_gateway_entry_identity(hass, entry, coordinator)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Inepro Metering config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    coordinator = entry.runtime_data
    await coordinator.async_shutdown()

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow manual removal only for devices no longer represented in entry data."""
    del hass
    configured_identifiers = _configured_device_identifiers(entry)
    return configured_identifiers.isdisjoint(device_entry.identifiers)


def _derive_entry_serial_number(data: dict[str, Any], *, title: str) -> str | None:
    """Derive the persisted serial number for one config entry when possible."""
    configured_serial = str(data.get(CONF_SERIAL_NUMBER, "")).strip()
    if configured_serial:
        return configured_serial

    for candidate in (data.get(CONF_NAME), title):
        if not isinstance(candidate, str):
            continue
        parsed_serial = parse_grow_serial_number(candidate.strip())
        if parsed_serial is not None:
            return parsed_serial.serial_number

    return None


def _async_update_gateway_entry_identity(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: IneproMeteringCoordinator | IneproSerialBusCoordinator,
) -> None:
    """Persist gateway serial and hub title after runtime validation."""
    if not entry_supports_gateway_management(entry):
        return

    coordinator_data = coordinator.data
    gateway = None if coordinator_data is None else coordinator_data.gateway
    if gateway is None or not gateway.serial_number:
        return

    new_data = dict(entry.data)
    new_data[CONF_SERIAL_NUMBER] = gateway.serial_number
    new_title = gateway_display_name(entry, gateway=gateway)
    if new_title != entry.title or new_data.get(CONF_SERIAL_NUMBER) != entry.data.get(
        CONF_SERIAL_NUMBER
    ):
        hass.config_entries.async_update_entry(entry, title=new_title, data=new_data)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy entries to the latest config-entry schema."""
    new_data = dict(entry.data)
    new_version = entry.version

    if new_version < 2 and (
        TransportType(entry.data[CONF_TRANSPORT]) is TransportType.SERIAL
        and CONF_METERS not in entry.data
    ):
        parsed_serial = parse_grow_serial_number(entry.title)
        new_data = {
            key: value
            for key, value in entry.data.items()
            if key not in {CONF_VARIANT, CONF_SLAVE_ID}
        }
        new_data[CONF_METERS] = [
            serialize_configured_meter(
                ConfiguredMeter(
                    family=str(entry.data[CONF_FAMILY]),
                    name=entry.title,
                    variant=str(entry.data[CONF_VARIANT]),
                    slave_id=int(entry.data[CONF_SLAVE_ID]),
                    serial_number=parsed_serial.serial_number
                    if parsed_serial
                    else None,
                    product_code=parsed_serial.product_code if parsed_serial else None,
                )
            )
        ]
        new_version = 2
    elif new_version < 2:
        new_version = 2

    if new_version < 3:
        if CONF_METERS not in new_data:
            serial_number = _derive_entry_serial_number(new_data, title=entry.title)
            if serial_number is not None:
                new_data[CONF_SERIAL_NUMBER] = serial_number
        new_version = 3

    if new_version < 4:
        if CONF_METERS in new_data:
            new_data[CONF_METERS] = [
                serialize_configured_meter(meter)
                for meter in get_configured_meters(new_data, title=entry.title)
            ]
        elif CONF_ROUTES not in new_data or CONF_ACTIVE_ROUTE not in new_data:
            new_data = with_routes_applied(
                new_data,
                routes=(build_route_from_entry_data(new_data),),
            )
        new_version = 4

    if new_version < 5:
        if CONF_METERS in new_data:
            new_data[CONF_METERS] = [
                serialize_configured_meter(
                    ensure_bus_meter_routes(meter, bus_entry_data=new_data)
                )
                for meter in get_configured_meters(new_data, title=entry.title)
            ]
        new_version = 5

    if new_data != entry.data or new_version != entry.version:
        hass.config_entries.async_update_entry(
            entry, data=new_data, version=new_version
        )

    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register Inepro domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_WIFI_CREDENTIALS):
        return

    async def async_handle_set_wifi_credentials(call: ServiceCall) -> None:
        """Handle a set Wi-Fi credentials service call."""
        await _async_handle_set_wifi_credentials(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_WIFI_CREDENTIALS,
        async_handle_set_wifi_credentials,
        schema=SET_WIFI_CREDENTIALS_SCHEMA,
    )


async def _async_handle_set_wifi_credentials(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Write Wi-Fi credentials to a configured GROW meter."""
    serial_number = str(call.data[CONF_SERIAL_NUMBER]).strip()
    target = _validate_wifi_service_target(hass, serial_number)

    try:
        await target.coordinator.async_set_wifi_credentials(
            slave_id=target.meter.slave_id,
            ssid=str(call.data[CONF_SSID]),
            password=str(call.data[CONF_PASSWORD]),
            apply=bool(call.data[CONF_APPLY]),
            meter_key=build_meter_key(target.meter),
        )
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=EXC_WIFI_CREDENTIALS_INVALID,
            translation_placeholders={"error": str(err)},
        ) from err
    except IneproMeteringError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=EXC_WIFI_CREDENTIALS_WRITE_FAILED,
            translation_placeholders={"serial_number": serial_number},
        ) from err


def _validate_wifi_service_target(
    hass: HomeAssistant,
    serial_number: str,
) -> _WiFiServiceTarget:
    """Return the writable service target or raise a validation error."""
    target = _find_wifi_service_target(hass, serial_number)
    if target is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=EXC_WIFI_CREDENTIALS_METER_NOT_FOUND,
            translation_placeholders={"serial_number": serial_number},
        )

    profile = get_profile(target.meter.family, target.meter.variant)
    if TransportType.TCP_WIFI not in profile.supported_transports:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=EXC_WIFI_CREDENTIALS_UNSUPPORTED,
            translation_placeholders={
                "serial_number": serial_number,
                "model": profile.title,
            },
        )
    return target


def _find_wifi_service_target(
    hass: HomeAssistant,
    serial_number: str,
) -> _WiFiServiceTarget | None:
    """Find the live coordinator route for a configured meter serial."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        meter = _find_matching_meter(entry, serial_number)
        if meter is None:
            continue

        coordinator = getattr(entry, "runtime_data", None)
        if entry.state is not ConfigEntryState.LOADED or coordinator is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=EXC_WIFI_CREDENTIALS_NOT_LOADED,
                translation_placeholders={"serial_number": serial_number},
            )

        return _WiFiServiceTarget(coordinator=coordinator, meter=meter)

    return None


def _find_matching_meter(
    entry: ConfigEntry, serial_number: str
) -> ConfiguredMeter | None:
    """Return the configured meter matching a Wi-Fi service serial number."""
    for meter in get_configured_meters(entry.data, title=entry.title):
        known_serials = {
            build_meter_key(meter),
            meter.name,
        }
        if meter.serial_number is not None:
            known_serials.add(meter.serial_number)
        if serial_number in known_serials:
            return meter

    return None


def _configured_device_identifiers(entry: ConfigEntry) -> set[tuple[str, str]]:
    """Return the device identifiers currently represented by one config entry."""
    if not is_bus_entry(entry.data):
        configured_meters = get_configured_meters(entry.data, title=entry.title)
        meter = configured_meters[0] if configured_meters else None
        identifiers = {
            meter_device_identifier(
                entry,
                serial_number=(
                    None
                    if entry_supports_gateway_management(entry) or meter is None
                    else meter.serial_number
                ),
            )
        }
        if entry_supports_gateway_management(entry):
            identifiers.add(gateway_device_identifier(entry))
        return identifiers

    identifiers: set[tuple[str, str]] = set()
    configured_meters = get_configured_meters(entry.data, title=entry.title)
    primary_meter = configured_meters[0] if configured_meters else None
    for meter in configured_meters:
        identifiers.add(
            configured_meter_device_identifier(
                entry,
                meter,
                fallback_key=(
                    entry.entry_id
                    if meter == primary_meter
                    else f"{entry.entry_id}:{build_meter_key(meter)}"
                ),
            )
        )

    if entry_supports_gateway_management(entry):
        identifiers.add(gateway_device_identifier(entry))

    return identifiers
