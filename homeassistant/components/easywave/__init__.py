"""The Easywave integration."""

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_PID,
    DOMAIN,
    EasywaveGatewayFeature as EasywaveGatewayFeature,
    EasywaveTransmitterFeature as EasywaveTransmitterFeature,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)
from .coordinator import EasywaveCoordinator
from .devices import iter_device_buckets
from .gateway_device import update_gateway_device
from .transceiver import RX11Transceiver

_LOGGER = logging.getLogger(__name__)


@dataclass
class EasywaveRuntimeData:
    """Runtime data for the Easywave integration."""

    coordinator: EasywaveCoordinator


type EasywaveConfigEntry = ConfigEntry[EasywaveRuntimeData]

# Platform registered for this integration. USB connectivity is handled in
# __init__.py / coordinator / transceiver / config_flow, not here.
_PLATFORMS: list[Platform] = [Platform.SENSOR]


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

    entry.runtime_data = EasywaveRuntimeData(coordinator=coordinator)

    update_gateway_device(hass, entry, transceiver)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> None:
    """Reload the entry when device subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Unload the gateway config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.async_shutdown()
    return unload_ok


def _device_identifier(device: dr.DeviceEntry) -> str | None:
    """Return the Easywave identifier stored on a device registry entry."""
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            return identifier
    return None


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: EasywaveConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Handle removal of a device via the three-dot menu.

    The RX11 gateway device (identifier == entry_id) cannot be removed here;
    the user must remove the whole config entry instead. Child devices are
    removed from their device-type bucket subentry.
    """
    if (DOMAIN, config_entry.entry_id) in device_entry.identifiers:
        return False

    easywave_id = _device_identifier(device_entry)
    if easywave_id is None:
        return False

    for subentry in iter_device_buckets(config_entry):
        devices = subentry.data.get(CONF_DEVICES)
        if not isinstance(devices, dict) or easywave_id not in devices:
            continue
        updated_devices = dict(devices)
        del updated_devices[easywave_id]
        if updated_devices:
            hass.config_entries.async_update_subentry(
                config_entry,
                subentry,
                data={CONF_DEVICES: updated_devices},
            )
        else:
            hass.config_entries.async_remove_subentry(
                config_entry, subentry.subentry_id
            )
        return True

    return False
