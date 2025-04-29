"""Common tools."""

import base64
from io import BytesIO
import logging

from PIL import Image
import requests

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import AwtrixCoordinator

_LOGGER = logging.getLogger(__name__)

def getIcon(url):
    """Get icon by url."""
    try:
        timeout = 5
        response = requests.get(url, timeout=timeout)
        if response and response.status_code == 200:
            pil_im = Image.open(BytesIO(response.content))
            pil_im = pil_im.convert('RGB')
            b = BytesIO()
            pil_im.save(b, 'jpeg')
            im_bytes = b.getvalue()
            return base64.b64encode(im_bytes).decode()
    except Exception:  # noqa: BLE001
        _LOGGER.error("Failed to get ICON %s: action", url)

@callback
def async_get_coordinator_by_device_id(
    hass: HomeAssistant, device_id: str
) -> AwtrixCoordinator:
    """Get the Awtrix coordinator for this device ID."""
    device_registry = dr.async_get(hass)

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ValueError(f"Unknown Awtrix device ID: {device_id}")

    for entry_id in device_entry.config_entries:
        if (
            (entry := hass.config_entries.async_get_entry(entry_id))
            and entry.domain == DOMAIN
        ):
            coordinator = entry.runtime_data.coordinator
            if coordinator.config_entry.entry_id == entry_id:
                return coordinator

    raise ValueError(f"No coordinator for device ID: {device_id}")

@callback
def async_get_coordinator_by_device_name(
    hass: HomeAssistant, device_names: list[str]
) -> AwtrixCoordinator:
    """Get the Awtrix coordinator for this device name."""

    result = []
    device_registry = dr.async_get(hass)
    for device in device_registry.devices.values():
        if device.manufacturer == 'Blueforcer':
            if device.name in device_names or device.name_by_user or device.name in device_names:
                for entry_id in device.config_entries:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    if entry.domain == DOMAIN:
                        result.append(entry.runtime_data.coordinator)

    return result

@callback
def async_get_coordinator_devices(
    hass: HomeAssistant,
) -> AwtrixCoordinator:
    """Get the Awtrix coordinator for this device ID."""

    result = []
    device_registry = dr.async_get(hass)
    for device in device_registry.devices.values():
        if device.manufacturer == 'Blueforcer':
            for  entry_id in device.config_entries:
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry.domain == DOMAIN:
                    result.append(entry.runtime_data.coordinator)

    return result
