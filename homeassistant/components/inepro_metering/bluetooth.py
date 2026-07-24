"""Home Assistant Bluetooth discovery helpers for Inepro Metering."""

import logging
from typing import Any

from inepro_metering.ble import async_read_ble_device_information_only

from homeassistant.components import bluetooth as ha_bluetooth
from homeassistant.const import CONF_TIMEOUT
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_TRANSPORT,
    DEFAULT_BLUETOOTH_TIMEOUT,
    TransportType,
)
from .discovery import (
    DiscoveredGrowBluetoothMeter,
    async_discover_grow_bluetooth_proxy_meters,
    infer_grow_variant,
    parse_grow_bluetooth_name,
)
from .modbus import (
    BLUETOOTH_PAIRING_MODE_NEVER,
    CONF_BLE_CLIENT_FACTORY,
    CONF_BLUETOOTH_DEVICE,
    CONF_BLUETOOTH_DEVICE_RESOLVER,
    CONF_BLUETOOTH_PAIRING_MODE,
    IneproConnectionError,
)
from .models import MeterFamily, get_profile

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "DiscoveredGrowBluetoothMeter",
    "IneproBluetoothDeviceNotFound",
    "async_discover_grow_bluetooth_meters",
    "async_discover_grow_bluetooth_proxy_meters",
    "async_entry_data_with_ha_ble_device",
    "async_read_bluetooth_device_information",
    "grow_bluetooth_meter_from_service_info",
]


class IneproBluetoothDeviceNotFound(IneproConnectionError):
    """Raised when Home Assistant has no current connectable BLEDevice."""


def async_discover_grow_bluetooth_meters(
    hass: HomeAssistant,
) -> tuple[DiscoveredGrowBluetoothMeter, ...]:
    """Return connectable GROW meters from Home Assistant's Bluetooth cache."""
    discovered: dict[str, DiscoveredGrowBluetoothMeter] = {}

    try:
        service_infos = ha_bluetooth.async_discovered_service_info(
            hass,
            connectable=True,
        )
    except RuntimeError:
        return ()

    for service_info in service_infos:
        meter = grow_bluetooth_meter_from_service_info(service_info)
        if meter is None:
            continue
        _LOGGER.debug(
            "Bluetooth discovery parsed GROW meter serial=%s address=%s name=%s rssi=%s",
            meter.serial_number,
            meter.address,
            meter.bluetooth_name,
            meter.rssi,
        )
        previous = discovered.get(meter.serial_number)
        if previous is None or _rssi_value(meter.rssi) > _rssi_value(previous.rssi):
            discovered[meter.serial_number] = meter

    return tuple(sorted(discovered.values(), key=lambda meter: meter.serial_number))


def async_entry_data_with_ha_ble_device(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    *,
    require_device: bool = True,
    pairing_mode: str | None = "",
) -> dict[str, Any]:
    """Return runtime config enriched with a current Home Assistant BLEDevice."""
    config = dict(entry_data)
    if TransportType(config[CONF_TRANSPORT]) is not TransportType.BLUETOOTH:
        return config

    address = str(config[CONF_BLUETOOTH_ADDRESS]).strip()

    def resolve_ble_device() -> Any | None:
        """Resolve the latest connectable BLEDevice from Home Assistant."""
        return ha_bluetooth.async_ble_device_from_address(
            hass,
            address,
            connectable=True,
        )

    config[CONF_BLUETOOTH_DEVICE_RESOLVER] = resolve_ble_device
    if pairing_mode == "":
        pairing_mode = BLUETOOTH_PAIRING_MODE_NEVER
    if pairing_mode is None:
        config.pop(CONF_BLUETOOTH_PAIRING_MODE, None)
    else:
        config.setdefault(CONF_BLUETOOTH_PAIRING_MODE, pairing_mode)
    ble_device = resolve_ble_device()
    if ble_device is None:
        _LOGGER.debug(
            "Home Assistant has no current connectable BLEDevice for address=%s",
            address,
        )
        config.pop(CONF_BLUETOOTH_DEVICE, None)
        if require_device:
            raise IneproBluetoothDeviceNotFound(
                f"No connectable BLEDevice found for {address}"
            )
        return config

    _LOGGER.debug(
        "Resolved Home Assistant BLEDevice for address=%s name=%s",
        address,
        getattr(ble_device, "name", None),
    )
    config[CONF_BLUETOOTH_DEVICE] = ble_device
    return config


async def async_read_bluetooth_device_information(entry_data: dict[str, Any]):
    """Read direct Bluetooth GATT Device Information without Modbus pairing."""
    if TransportType(entry_data[CONF_TRANSPORT]) is not TransportType.BLUETOOTH:
        return None

    try:
        return await async_read_ble_device_information_only(
            address=str(entry_data[CONF_BLUETOOTH_ADDRESS]),
            name=str(
                entry_data.get(CONF_BLUETOOTH_NAME)
                or entry_data[CONF_BLUETOOTH_ADDRESS]
            ),
            timeout=float(entry_data.get(CONF_TIMEOUT, DEFAULT_BLUETOOTH_TIMEOUT)),
            ble_device=entry_data.get(CONF_BLUETOOTH_DEVICE),
            ble_device_resolver=entry_data.get(CONF_BLUETOOTH_DEVICE_RESOLVER),
            client_factory=entry_data.get(CONF_BLE_CLIENT_FACTORY),
        )
    except Exception as err:
        raise IneproConnectionError("Failed to read BLE Device Information") from err


def grow_bluetooth_meter_from_service_info(
    service_info: Any,
) -> DiscoveredGrowBluetoothMeter | None:
    """Parse one Home Assistant Bluetooth discovery object into a GROW meter."""
    bluetooth_name = str(getattr(service_info, "name", "") or "").strip()
    parsed = parse_grow_bluetooth_name(bluetooth_name)
    if parsed is None:
        return None

    variant = infer_grow_variant(parsed.serial_number, parsed.product_code)
    if variant is None:
        return None

    profile = get_profile(MeterFamily.GROW, variant)
    address = getattr(service_info, "address", None)
    if address is None:
        return None
    return DiscoveredGrowBluetoothMeter(
        address=str(address),
        bluetooth_name=bluetooth_name,
        serial_number=parsed.serial_number,
        variant=variant,
        model_title=profile.title,
        product_code=parsed.product_code,
        rssi=getattr(service_info, "rssi", None),
    )


def _rssi_value(rssi: int | None) -> int:
    """Normalize missing RSSI for best-advertisement comparisons."""
    return -999 if rssi is None else int(rssi)
