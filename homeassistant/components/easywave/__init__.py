"""The Easywave integration."""

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    DOMAIN,
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

# All platforms that any device type might use.  Every platform's
# async_setup_entry iterates entry.options["devices"] to create only the
# entities relevant to its device type.
_ALL_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.SWITCH,
]


def get_devices(entry: EasywaveConfigEntry) -> list[EasywaveDeviceEntry]:
    """Return all device configurations stored in entry options."""
    return [
        EasywaveDeviceEntry(
            subentry_id=d["id"],
            title=d["title"],
            data=d["data"],
        )
        for d in entry.options.get("devices", [])
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

    legacy = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_rx11")}
    )
    if legacy is not None:
        device_registry.async_remove_device(legacy.id)


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
    # Add update listener so that adding/removing devices via the options flow
    # triggers a reload, which causes platforms to re-discover the new/removed entities.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, _ALL_PLATFORMS)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> None:
    """Reload the entry when options (device list) change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _purge_legacy_binary_sensor_entities(
    hass: HomeAssistant, entry: EasywaveConfigEntry
) -> None:
    """Remove orphaned binary_sensor entities from a version-1 config entry.

    Version 1 exposed transmitter buttons, channels and battery state as
    binary_sensor entities.  Version 2 replaced those with enum sensor and
    event entities, but the registry entries persist and must be purged
    explicitly.  Channel binary sensors for type-2 transmitters are not
    affected because they only exist in version 2+ entries.
    """
    entity_registry = er.async_get(hass)
    stale = [
        entry_entity.entity_id
        for entry_entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if entry_entity.domain == "binary_sensor"
    ]
    for entity_id in stale:
        entity_registry.async_remove(entity_id)
        _LOGGER.debug("Removed legacy binary_sensor entity %s", entity_id)


async def async_migrate_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Handle migration of config entry versions."""
    if entry.version < 2:
        # Version 1 → 2: Remove orphaned binary_sensor entities (transmitter
        # buttons, channels, battery) replaced by enum sensors and event entities.
        _purge_legacy_binary_sensor_entities(hass, entry)
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Unload the gateway config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _ALL_PLATFORMS)
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
    the user must remove the whole config entry instead.  All other devices
    (transmitters, receivers, sensors) are stored in entry.options["devices"]
    and can be removed freely.
    """
    # The gateway device uses entry_id as its identifier.
    if (DOMAIN, config_entry.entry_id) in device_entry.identifiers:
        return False

    # Find the matching subentry_id from the device identifiers.
    device_subentry_id = next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    if device_subentry_id is None:
        return False

    new_devices = [
        d
        for d in config_entry.options.get("devices", [])
        if d["id"] != device_subentry_id
    ]
    hass.config_entries.async_update_entry(
        config_entry,
        options={**config_entry.options, "devices": new_devices},
    )
    return True
