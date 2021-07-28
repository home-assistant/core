"""Home Assistant wrapper for a pyWeMo device."""
import logging

from pywemo import WeMoDevice
from pywemo.subscribe import EVENT_TYPE_LONG_PRESS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_PARAMS,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import DOMAIN, SIGNAL_WEMO_STATE_PUSH, WEMO_SUBSCRIPTION_EVENT

_LOGGER = logging.getLogger(__name__)


class DeviceWrapper:
    """Home Assistant wrapper for a pyWeMo device."""

    def __init__(self, hass: HomeAssistant, wemo: WeMoDevice, device_id: str) -> None:
        """Initialize DeviceWrapper."""
        self.hass = hass
        self.wemo = wemo
        self.device_id = device_id
        self.device_info = _device_info(wemo)
        self.supports_long_press = wemo.supports_long_press()

    def subscription_callback(
        self, _device: WeMoDevice, event_type: str, params: str
    ) -> None:
        """Receives push notifications from WeMo devices."""
        if event_type == EVENT_TYPE_LONG_PRESS:
            self.hass.bus.fire(
                WEMO_SUBSCRIPTION_EVENT,
                {
                    CONF_DEVICE_ID: self.device_id,
                    CONF_NAME: self.wemo.name,
                    CONF_TYPE: event_type,
                    CONF_PARAMS: params,
                    CONF_UNIQUE_ID: self.wemo.serialnumber,
                },
            )
        else:
            dispatcher_send(
                self.hass, SIGNAL_WEMO_STATE_PUSH, self.device_id, event_type, params
            )


def _device_info(wemo: WeMoDevice):
    return {
        "name": wemo.name,
        "identifiers": {(DOMAIN, wemo.serialnumber)},
        "model": wemo.model_name,
        "manufacturer": "Belkin",
    }


async def async_register_device(
    hass: HomeAssistant, config_entry: ConfigEntry, wemo: WeMoDevice
) -> DeviceWrapper:
    """Register a device with home assistant and enable pywemo event callbacks."""
    device_registry = async_get_device_registry(hass)
    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, **_device_info(wemo)
    )

    registry = hass.data[DOMAIN]["registry"]
    await hass.async_add_executor_job(registry.register, wemo)

    device = DeviceWrapper(hass, wemo, entry.id)
    hass.data[DOMAIN].setdefault("devices", {})[entry.id] = device
    registry.on(wemo, None, device.subscription_callback)

    if device.supports_long_press:
        try:
            await hass.async_add_executor_job(wemo.ensure_long_press_virtual_device)
        # Temporarily handling all exceptions for #52996 & pywemo/pywemo/issues/276
        # Replace this with `except: PyWeMoException` after upstream has been fixed.
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Failed to enable long press support for device: %s", wemo.name
            )
            device.supports_long_press = False

    return device


@callback
def async_get_device(hass: HomeAssistant, device_id: str) -> DeviceWrapper:
    """Return DeviceWrapper for device_id."""
    return hass.data[DOMAIN]["devices"][device_id]
