"""The Easywave integration."""

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.loader import async_get_integration

from .const import (
    CONF_DEVICE_DATA,
    CONF_DEVICE_PATH,
    CONF_DEVICE_TITLE,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    DOMAIN,
    EasywaveGatewayFeature as EasywaveGatewayFeature,
    EasywaveTransmitterFeature as EasywaveTransmitterFeature,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)
from .coordinator import EasywaveCoordinator
from .entity import EasywaveDeviceEntry
from .transceiver import RX11Transceiver

_LOGGER = logging.getLogger(__name__)


@dataclass
class EasywaveRuntimeData:
    """Runtime data for the Easywave integration."""

    coordinator: EasywaveCoordinator
    frequency: str | None
    country: str | None


type EasywaveConfigEntry = ConfigEntry[EasywaveRuntimeData]

# Platform registered for this integration. USB connectivity is handled in
# __init__.py / coordinator / transceiver / config_flow, not here.
_PLATFORMS: list[Platform] = [Platform.SENSOR]


def get_devices(entry: EasywaveConfigEntry) -> list[EasywaveDeviceEntry]:
    """Return all device configurations stored in config entry options."""
    return [
        EasywaveDeviceEntry(
            device_id=device[CONF_DEVICE_ID],
            title=device[CONF_DEVICE_TITLE],
            data=dict(device[CONF_DEVICE_DATA]),
        )
        for device in entry.options.get(CONF_DEVICES, [])
    ]


def _register_gateway_device(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    transceiver: RX11Transceiver,
) -> None:
    """Create or update the RX11 gateway device in the device registry."""
    serial_number = transceiver.usb_serial_number
    if not isinstance(serial_number, str):
        serial_number = entry.data.get(CONF_USB_SERIAL_NUMBER)

    hw_version = transceiver.hw_version
    if not isinstance(hw_version, str):
        hw_version = None

    sw_version = transceiver.fw_version
    if not isinstance(sw_version, str):
        sw_version = None

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_USB_PRODUCT) or "RX11 USB Transceiver",
        manufacturer=entry.data.get(CONF_USB_MANUFACTURER) or "ELDAT",
        model=entry.data.get(CONF_USB_PRODUCT) or "RX11 USB Transceiver",
        serial_number=serial_number,
        hw_version=hw_version,
        sw_version=sw_version,
    )


async def async_setup_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Set up the Easywave gateway config entry."""
    usb_pid = entry.data.get(CONF_USB_PID)
    frequency = get_frequency_for_pid(usb_pid)
    country_code = hass.config.country

    if frequency and not is_country_allowed_for_frequency(frequency, country_code):
        _LOGGER.warning(
            "This hardware operates on %s, which is not permitted in "
            "your configured region (%s). Integration disabled for regulatory compliance",
            frequency,
            country_code or "unknown",
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"frequency_not_permitted_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="frequency_not_permitted",
            translation_placeholders={
                "frequency": frequency,
                "country": country_code or "unknown",
            },
        )
        return False

    ir.async_delete_issue(hass, DOMAIN, f"frequency_not_permitted_{entry.entry_id}")

    transceiver = RX11Transceiver(hass, entry.data.get(CONF_DEVICE_PATH))
    coordinator = EasywaveCoordinator(hass, transceiver, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = EasywaveRuntimeData(
        coordinator=coordinator,
        frequency=frequency,
        country=country_code,
    )

    _register_gateway_device(hass, entry, transceiver)
    # Reload when devices are added or removed via the subentry flow.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_platform("device_trigger")
    await integration.async_get_platform("trigger")
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> None:
    """Reload the entry when options (device list) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Unload the gateway config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.async_shutdown()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: EasywaveConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Handle removal of a device via the three-dot menu.

    The RX11 gateway device (identifier == entry_id) cannot be removed here;
    the user must remove the whole config entry instead. Child devices are
    stored in config entry options and can be removed freely.
    """
    # The gateway device uses entry_id as its identifier.
    if (DOMAIN, config_entry.entry_id) in device_entry.identifiers:
        return False

    device_id = next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    if device_id is None:
        return False

    devices = config_entry.options.get(CONF_DEVICES, [])
    if not any(device[CONF_DEVICE_ID] == device_id for device in devices):
        return False

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **config_entry.options,
            CONF_DEVICES: [
                device for device in devices if device[CONF_DEVICE_ID] != device_id
            ],
        },
    )
    return True
