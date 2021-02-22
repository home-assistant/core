"""Common utilities for VeSync Component."""
import logging

from homeassistant.helpers.entity import ToggleEntity

from .const import VS_FANS, VS_LIGHTS, VS_SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_process_devices(hass, manager):
    """Assign devices to proper component."""
    devices = {}
    devices[VS_SWITCHES] = []
    devices[VS_FANS] = []
    devices[VS_LIGHTS] = []

    await hass.async_add_executor_job(manager.update)

    if manager.fans:
        devices[VS_FANS].extend(manager.fans)
        _LOGGER.info("%d VeSync fans found", len(manager.fans))

    if manager.outlets:
        devices[VS_SWITCHES].extend(manager.outlets)
        _LOGGER.info("%d VeSync outlets found", len(manager.outlets))

    if manager.switches:
        for switch in manager.switches:
            if not switch.is_dimmable():
                devices[VS_SWITCHES].append(switch)
            else:
                devices[VS_LIGHTS].append(switch)
        _LOGGER.info("%d VeSync switches found", len(manager.switches))

    return devices


class VeSyncDevice(ToggleEntity):
    """Base class for VeSync Device Representations."""

    def __init__(self, device):
        """Initialize the VeSync device."""
        self.device = device

    @property
    def unique_id(self):
        """Return the ID of this device."""
        if isinstance(self.device.sub_device_no, int):
            return "{}{}".format(self.device.cid, str(self.device.sub_device_no))
        return self.device.cid

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.device_name

    @property
    def is_on(self):
        """Return True if device is on."""
        return self.device.device_status == "on"

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.device.connection_status == "online"

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.device.turn_off()

    def update(self):
        """Update vesync device."""
        self.device.update()
