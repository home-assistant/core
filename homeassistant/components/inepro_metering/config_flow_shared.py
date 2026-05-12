"""Shared helpers and constants for the Inepro Metering config flow."""

from collections.abc import Awaitable, Callable
from typing import Any

from inepro_metering.ble import (
    BleGattDeviceInformation,
    IneproBleDeviceInformationMissingError,
    IneproBleDeviceNotFoundError,
    IneproBlePairingFailedError,
    IneproBlePairingUnsupportedError,
    IneproBleServicesMissingError,
    is_ble_pairing_trigger_error,
)

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT

from .bluetooth import (
    DiscoveredGrowBluetoothMeter,
    async_read_bluetooth_device_information,
)
from .const import (
    CONF_BAUDRATE,
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_BYTESIZE,
    CONF_FAMILY,
    CONF_PARITY,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TRANSPORT,
    DEFAULT_BLUETOOTH_PAIRING_TIMEOUT,
    SHOW_EXPERIMENTAL_TRANSPORTS,
    MeterFamily,
    TransportType,
)
from .discovery import (
    DiscoveredGrowMeter,
    GrowSerialNumber,
    async_read_grow_serial_number,
    parse_grow_serial_number,
)
from .entry_data import ConfiguredMeter, build_meter_key
from .modbus import (
    BLUETOOTH_PAIRING_MODE_AUTO,
    BLUETOOTH_PAIRING_MODE_NEVER,
    CONF_BLUETOOTH_FORCE_REPAIR,
    CONF_BLUETOOTH_PAIRING_MODE,
    CONF_BLUETOOTH_PAIRING_TIMEOUT,
    IneproBluetoothNotPairedError,
    IneproConnectionError,
    IneproModbusClient,
    IneproReadError,
)

CONFIG_ENTRY_VERSION = 5

CONF_DISCOVERED_METERS = "discovered_meters"
CONF_DISCOVERED_BLUETOOTH_METER = "discovered_bluetooth_meter"
CONF_ACTION = "action"
CONF_SELECTED_ROUTE = "selected_route"
CONF_RESET_BLUETOOTH_PAIRING = "reset_bluetooth_pairing"
CONF_BLUETOOTH_PAIRING_PIN = "bluetooth_pairing_pin"
CONF_SELECTED_METER = "selected_meter"

OPTION_ACTION_UPDATE_POLLING = "update_polling"
OPTION_ACTION_SCAN_SERIAL = "scan_serial"
OPTION_ACTION_UPDATE_CONNECTION = "update_connection"
OPTION_ACTION_EDIT_SERIAL_BUS = "edit_serial_bus"
OPTION_ACTION_ADD_ROUTE = "add_route"
OPTION_ACTION_SWITCH_ROUTE = "switch_route"
OPTION_ACTION_MANAGE_METER_ROUTES = "manage_meter_routes"

EXPERIMENTAL_TRANSPORTS = {
    TransportType.BLUETOOTH_PROXY,
}


class IneproIdentityError(Exception):
    """Raised when a transport update reaches a different physical meter."""


def configured_entry_serial_number(entry_data: dict[str, Any]) -> str | None:
    """Return the configured serial number for this entry when known."""
    serial_number = entry_data.get(CONF_SERIAL_NUMBER)
    if isinstance(serial_number, str):
        normalized_serial = serial_number.strip()
        if normalized_serial:
            return normalized_serial

    configured_name = str(entry_data.get(CONF_NAME, "")).strip()
    parsed_serial = parse_grow_serial_number(configured_name)
    if parsed_serial is not None:
        return parsed_serial.serial_number
    return None


def configured_grow_serial(entry_data: dict[str, Any]) -> GrowSerialNumber | None:
    """Return the configured GROW serial object when this entry represents a GROW meter."""
    serial_number = configured_entry_serial_number(entry_data)
    if serial_number is None:
        return None
    return parse_grow_serial_number(serial_number)


async def async_read_detected_grow_serial(
    entry_data: dict[str, Any],
    *,
    product_code: str | None = None,
    modbus_client_factory: Callable[[dict[str, Any]], Any] = IneproModbusClient,
) -> str | None:
    """Read the live GROW serial number directly from the meter."""
    client = modbus_client_factory(entry_data)
    try:
        return await async_read_grow_serial_number(
            client,
            slave_id=int(entry_data[CONF_SLAVE_ID]),
            product_code=product_code,
        )
    except IneproBluetoothNotPairedError:
        raise
    except (IneproConnectionError, IneproReadError, TypeError, ValueError) as err:
        raise IneproConnectionError("Failed to read meter serial number") from err
    finally:
        await client.async_close()


async def async_resolve_entry_serial_number_for_creation(
    entry_data: dict[str, Any],
    *,
    read_detected_grow_serial: Callable[..., Awaitable[str | None]] = (
        async_read_detected_grow_serial
    ),
) -> str | None:
    """Resolve the serial number to persist for a new config entry."""
    if entry_data.get(CONF_FAMILY) == MeterFamily.GROW.value:
        configured_serial = configured_grow_serial(entry_data)
        product_code = (
            None if configured_serial is None else configured_serial.product_code
        )
        return await read_detected_grow_serial(
            entry_data,
            product_code=product_code,
        )

    return configured_entry_serial_number(entry_data)


async def async_validate_entry_identity(
    entry_data: dict[str, Any],
    *,
    read_detected_grow_serial: Callable[..., Awaitable[str | None]] = (
        async_read_detected_grow_serial
    ),
) -> None:
    """Confirm that a re-targeted entry still points at the same GROW meter."""
    configured_serial = configured_grow_serial(entry_data)
    if configured_serial is None:
        return

    try:
        detected_serial = await read_detected_grow_serial(
            entry_data,
            product_code=configured_serial.product_code,
        )
    except IneproBluetoothNotPairedError:
        raise
    except IneproConnectionError as err:
        raise IneproConnectionError("Failed to validate meter identity") from err

    if detected_serial != configured_serial.serial_number:
        raise IneproIdentityError(
            "Configured entry "
            f"{configured_serial.serial_number} resolved to "
            f"{detected_serial or 'unknown'}"
        )


async def async_validate_bluetooth_gatt_identity(
    entry_data: dict[str, Any],
    *,
    read_bluetooth_device_information: Callable[
        [dict[str, Any]], Awaitable[BleGattDeviceInformation | None]
    ] = async_read_bluetooth_device_information,
) -> str | None:
    """Validate GROW BLE Device Information before Modbus-over-BLE writes."""
    if (
        TransportType(entry_data[CONF_TRANSPORT]) is not TransportType.BLUETOOTH
        or entry_data.get(CONF_FAMILY) != MeterFamily.GROW.value
    ):
        return None

    try:
        device_information = await read_bluetooth_device_information(entry_data)
    except IneproConnectionError:
        raise
    except Exception as err:
        raise IneproConnectionError("Failed to read BLE Device Information") from err

    if device_information is None:
        return None

    gatt_serial = normalize_grow_gatt_serial(device_information.serial_number)
    if gatt_serial is None:
        missing_serial = IneproBleDeviceInformationMissingError(
            "Missing BLE GATT serial number"
        )
        raise IneproConnectionError(
            "Missing BLE GATT serial number"
        ) from missing_serial

    configured_serial = configured_entry_serial_number(entry_data)
    if configured_serial is not None and gatt_serial != configured_serial:
        raise IneproIdentityError(
            "Configured entry "
            f"{configured_serial} resolved to GATT serial {gatt_serial}"
        )

    return gatt_serial


def normalize_grow_gatt_serial(serial_number: str | None) -> str | None:
    """Normalize a GROW GATT serial string for comparison with IM-<serial>."""
    if serial_number is None:
        return None
    text = str(serial_number).replace("\x00", "").strip()
    if not text:
        return None
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) >= 12:
        return digits[-12:]
    return text


def normalize_connection_data(
    transport: TransportType,
    user_input: dict[str, Any],
) -> dict[str, Any]:
    """Normalize selector values before storing the config entry."""
    data: dict[str, Any] = {
        CONF_TRANSPORT: transport.value,
        CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
    }

    if transport is TransportType.SERIAL:
        data.update(
            {
                CONF_SERIAL_PORT: str(user_input[CONF_SERIAL_PORT]).strip(),
                CONF_BAUDRATE: int(user_input[CONF_BAUDRATE]),
                CONF_BYTESIZE: int(user_input[CONF_BYTESIZE]),
                CONF_PARITY: str(user_input[CONF_PARITY]),
                CONF_STOPBITS: int(user_input[CONF_STOPBITS]),
            }
        )
        return data

    if transport is TransportType.BLUETOOTH:
        bluetooth_name = str(user_input.get(CONF_BLUETOOTH_NAME) or "").strip()
        data.update(
            {
                CONF_BLUETOOTH_ADDRESS: str(user_input[CONF_BLUETOOTH_ADDRESS]).strip(),
            }
        )
        if bluetooth_name:
            data[CONF_BLUETOOTH_NAME] = bluetooth_name
        return data

    if transport is TransportType.BLUETOOTH_PROXY:
        bluetooth_name = str(user_input.get(CONF_BLUETOOTH_NAME) or "").strip()
        data.update(
            {
                CONF_HOST: str(user_input[CONF_HOST]).strip(),
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_BLUETOOTH_ADDRESS: str(user_input[CONF_BLUETOOTH_ADDRESS]).strip(),
            }
        )
        if bluetooth_name:
            data[CONF_BLUETOOTH_NAME] = bluetooth_name
        return data

    data.update(
        {
            CONF_HOST: str(user_input[CONF_HOST]).strip(),
            CONF_PORT: int(user_input[CONF_PORT]),
        }
    )
    return data


def user_visible_transports(
    transports: tuple[TransportType, ...],
    *,
    include_transport: TransportType | None = None,
) -> tuple[TransportType, ...]:
    """Return transports shown in normal user-facing selectors."""
    if SHOW_EXPERIMENTAL_TRANSPORTS:
        return transports

    return tuple(
        transport
        for transport in transports
        if transport not in EXPERIMENTAL_TRANSPORTS or transport is include_transport
    )


def bluetooth_gatt_validation_data(entry_data: dict[str, Any]) -> dict[str, Any]:
    """Return temporary setup data for the no-pair GATT identity precheck."""
    validation_data = dict(entry_data)
    if TransportType(validation_data[CONF_TRANSPORT]) is TransportType.BLUETOOTH:
        validation_data.pop(CONF_BLUETOOTH_PAIRING_MODE, None)
        validation_data.pop(CONF_BLUETOOTH_PAIRING_TIMEOUT, None)
        validation_data.pop(CONF_BLUETOOTH_FORCE_REPAIR, None)
        validation_data.pop(CONF_BLUETOOTH_PAIRING_PIN, None)
    return validation_data


def bluetooth_modbus_pairing_validation_data(
    entry_data: dict[str, Any],
    *,
    force_repair: bool = False,
    pairing_pin: str | None = None,
) -> dict[str, Any]:
    """Return temporary setup data for encrypted Modbus-over-BLE validation."""
    validation_data = dict(entry_data)
    if TransportType(validation_data[CONF_TRANSPORT]) is TransportType.BLUETOOTH:
        normalized_pin = normalize_bluetooth_pairing_pin(pairing_pin)
        if force_repair or normalized_pin:
            validation_data[CONF_BLUETOOTH_PAIRING_MODE] = BLUETOOTH_PAIRING_MODE_AUTO
            validation_data[CONF_BLUETOOTH_PAIRING_TIMEOUT] = int(
                DEFAULT_BLUETOOTH_PAIRING_TIMEOUT
            )
        else:
            validation_data[CONF_BLUETOOTH_PAIRING_MODE] = BLUETOOTH_PAIRING_MODE_NEVER
            validation_data.pop(CONF_BLUETOOTH_PAIRING_TIMEOUT, None)
        if force_repair:
            validation_data[CONF_BLUETOOTH_FORCE_REPAIR] = True
        else:
            validation_data.pop(CONF_BLUETOOTH_FORCE_REPAIR, None)
        if normalized_pin:
            validation_data[CONF_BLUETOOTH_PAIRING_PIN] = normalized_pin
        else:
            validation_data.pop(CONF_BLUETOOTH_PAIRING_PIN, None)
    return validation_data


def bluetooth_pairing_validation_data(entry_data: dict[str, Any]) -> dict[str, Any]:
    """Return default temporary setup data for Modbus-over-BLE pairing."""
    return bluetooth_modbus_pairing_validation_data(entry_data)


def normalize_bluetooth_pairing_pin(pin: Any) -> str | None:
    """Normalize a user-entered GROW Bluetooth PIN."""
    if pin is None:
        return None
    normalized = str(pin).strip()
    if not normalized:
        return None
    if len(normalized) == 6 and normalized.isdigit():
        return normalized
    return ""


def connection_error_reason(
    err: IneproConnectionError,
    transport: TransportType,
) -> str:
    """Map transport-specific connection failures to config-flow error keys."""
    if transport is not TransportType.BLUETOOTH:
        return "cannot_connect"

    causes = tuple(_iter_exception_chain(err))
    if any(isinstance(cause, IneproBleDeviceNotFoundError) for cause in causes):
        return "bluetooth_device_not_found"
    if any(isinstance(cause, IneproBluetoothNotPairedError) for cause in causes):
        return "bluetooth_not_paired"
    if any(isinstance(cause, IneproBlePairingUnsupportedError) for cause in causes):
        return "bluetooth_pairing_unsupported"
    if any(isinstance(cause, IneproBlePairingFailedError) for cause in causes):
        return "bluetooth_pairing_failed"
    if any(isinstance(cause, IneproBleServicesMissingError) for cause in causes):
        return "bluetooth_services_missing"
    if any(isinstance(cause, TimeoutError) for cause in causes):
        return "bluetooth_timeout"
    return "bluetooth_cannot_connect"


def bluetooth_validation_error_reason(
    err: IneproConnectionError,
    transport: TransportType,
) -> str:
    """Map identity/read validation failures to user-facing BLE errors."""
    if transport is not TransportType.BLUETOOTH:
        return "cannot_validate"

    causes = tuple(_iter_exception_chain(err))
    if any(isinstance(cause, IneproBleDeviceNotFoundError) for cause in causes):
        return "bluetooth_device_not_found"
    if any(isinstance(cause, IneproBluetoothNotPairedError) for cause in causes):
        return "bluetooth_not_paired"
    if any(
        isinstance(cause, IneproBleDeviceInformationMissingError) for cause in causes
    ):
        return "unsupported_device"
    if any(isinstance(cause, IneproBlePairingUnsupportedError) for cause in causes):
        return "bluetooth_pairing_unsupported"
    if any(isinstance(cause, IneproBlePairingFailedError) for cause in causes):
        return "bluetooth_pairing_failed"
    if any(isinstance(cause, IneproBleServicesMissingError) for cause in causes):
        return "bluetooth_services_missing"
    if any(is_ble_pairing_trigger_error(cause) for cause in causes):
        return "bluetooth_not_paired"
    if any(_is_ble_modbus_response_timeout(cause) for cause in causes):
        return "bluetooth_not_paired"
    if any(isinstance(cause, TimeoutError) for cause in causes):
        return "bluetooth_timeout"
    return "cannot_validate"


def bluetooth_setup_identity_error_reason(
    err: IneproConnectionError,
    transport: TransportType,
) -> str:
    """Map config-flow BLE identity failures after GATT identity succeeds."""
    reason = bluetooth_validation_error_reason(err, transport)
    if transport is TransportType.BLUETOOTH and reason in {
        "cannot_validate",
        "bluetooth_pairing_failed",
    }:
        return "bluetooth_not_paired"
    return reason


def _iter_exception_chain(err: BaseException):
    """Yield an exception and its explicit/implicit cause chain."""
    seen: set[int] = set()
    current: BaseException | None = err
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_ble_modbus_response_timeout(err: BaseException) -> bool:
    """Return whether setup identity validation timed out after a BLE write."""
    return (
        isinstance(err, TimeoutError)
        and "timed out waiting for ble modbus response" in str(err).casefold()
    )


def build_unique_id(entry_data: dict[str, Any]) -> str:
    """Build a stable unique ID for one configured Modbus endpoint."""
    serial_number = configured_entry_serial_number(entry_data)
    if serial_number is not None:
        return serial_number

    transport = TransportType(entry_data[CONF_TRANSPORT])
    if transport is TransportType.SERIAL:
        endpoint = str(entry_data[CONF_SERIAL_PORT]).strip().upper()
    elif transport is TransportType.BLUETOOTH:
        endpoint = str(entry_data[CONF_BLUETOOTH_ADDRESS]).strip().upper()
    elif transport is TransportType.BLUETOOTH_PROXY:
        endpoint = (
            "BLEPROXY:"
            f"{str(entry_data[CONF_HOST]).strip().lower()}:"
            f"{int(entry_data[CONF_PORT])}:"
            f"{str(entry_data[CONF_BLUETOOTH_ADDRESS]).strip().upper()}"
        )
    else:
        endpoint = (
            f"{str(entry_data[CONF_HOST]).strip().lower()}:{int(entry_data[CONF_PORT])}"
        )

    return f"{endpoint}:{int(entry_data[CONF_SLAVE_ID])}"


def user_value(
    user_input: dict[str, Any] | None,
    key: str,
    default: Any,
) -> Any:
    """Return a previously entered value or a default."""
    if user_input is None:
        return default
    return user_input.get(key, default)


def discovered_meter_key(discovered_meter: DiscoveredGrowMeter) -> str:
    """Build a stable selector key for one discovered serial meter."""
    return f"{discovered_meter.serial_number}:{discovered_meter.slave_id}"


def bluetooth_meter_key(discovered_meter: DiscoveredGrowBluetoothMeter) -> str:
    """Build a stable selector key for one discovered Bluetooth meter."""
    return f"{discovered_meter.serial_number}:{discovered_meter.address}"


def meter_slave_id_field(meter: ConfiguredMeter) -> str:
    """Build the dynamic form field name for one meter's Modbus ID."""
    return f"Modbus ID for {build_meter_key(meter)}"
