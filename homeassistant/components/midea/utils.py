"""Utilities for the Midea integration."""

from midealocal.const import DeviceType
from midealocal.device import MideaDevice
from midealocal.devices.ac import DeviceAttributes as ACAttributes

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

# Older midea-local versions always reported these, so the entities were
# created for every device; now the device's capabilities decide.
_CAPABILITY_ENTITIES: dict[DeviceType, tuple[tuple[Platform, str], ...]] = {
    DeviceType.AC: (
        (Platform.SELECT, ACAttributes.rate_select),
        (Platform.SELECT, ACAttributes.wind_lr_angle),
        (Platform.SELECT, ACAttributes.wind_ud_angle),
        (Platform.SENSOR, ACAttributes.indoor_humidity),
        (Platform.SWITCH, ACAttributes.anion),
        (Platform.SWITCH, ACAttributes.screen_display),
        (Platform.SWITCH, ACAttributes.sound),
    ),
}


@callback
def async_remove_unsupported_entities(hass: HomeAssistant, device: MideaDevice) -> None:
    """Remove entities for capabilities the device does not report."""
    entity_registry = er.async_get(hass)
    for platform, attribute in _CAPABILITY_ENTITIES.get(device.device_type, ()):
        if attribute in device.attributes:
            continue
        if entity_id := entity_registry.async_get_entity_id(
            platform, DOMAIN, f"{device.device_id}_{attribute}"
        ):
            entity_registry.async_remove(entity_id)
