"""Support for VeSync humidifiers."""
import logging

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEVICE_CLASS_HUMIDIFIER,
    MODE_AUTO,
    MODE_SLEEP,
    SUPPORT_MODES,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import HUMI_DEV_TYPE_TO_HA, VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_HUMIDIFIERS

_LOGGER = logging.getLogger(__name__)

MANUAL_LOW = "manual low"
MANUAL_MID = "manual mid"
MANUAL_HIGH = "manual high"

PRESET_MODES = {
    "Classic300S": [MODE_AUTO, MODE_SLEEP, MANUAL_LOW, MANUAL_MID, MANUAL_HIGH],
    "Dual200S": [MODE_AUTO, MODE_SLEEP, MANUAL_LOW, MANUAL_MID, MANUAL_HIGH],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the VeSync humidifier platform."""

    async def async_discover(devices):
        """Add new devices to platform."""
        _async_setup_entities(devices, async_add_entities)

    disp = async_dispatcher_connect(
        hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), async_discover
    )
    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

    _async_setup_entities(hass.data[DOMAIN][VS_HUMIDIFIERS], async_add_entities)


@callback
def _async_setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    dev_list = []
    for dev in devices:
        if HUMI_DEV_TYPE_TO_HA.get(dev.device_type) == "humidifier":
            dev_list.append(VeSyncHumidifierHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(dev_list, update_before_add=True)


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": "Levoit",
            "model": self.device.device_type,
        }

    @property
    def is_on(self):
        """If the humidifier is currently on or off. `self.device.device_status` is always 'on' on this device."""
        return self.device.enabled

    @property
    def available_modes(self):
        """Return the list of available modes."""
        return PRESET_MODES[self.device.device_type]

    @property
    def device_class(self):
        """Return the device class type."""
        return DEVICE_CLASS_HUMIDIFIER

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        return 80

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        return 30

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MODES

    @property
    def mode(self):
        """Return the current mode, e.g., sleep, auto, manual."""
        mode = self.device.details["mode"]
        if mode == "manual":
            mist_level = self.device.details["mist_virtual_level"]
            level = " low"
            if mist_level < 4:
                level = " low"
            elif mist_level < 7:
                level = " mid"
            else:
                level = " high"
            mode += level
        return mode

    @property
    def target_humidity(self) -> int:
        """Return the desired humidity set point."""
        return self.device.config["auto_target_humidity"]

    @property
    def unique_info(self):
        """Return the ID of this humidifier."""
        return self.device.uuid

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the humidifier."""
        attr = {}
        attr["current_humidity"] = self.device.details["humidity"]
        attr["mist_virtual_level"] = self.device.details["mist_virtual_level"]
        attr["mist_level"] = self.device.details["mist_level"]
        attr["water_lacks"] = self.device.details["water_lacks"]
        attr["humidity_high"] = self.device.details["humidity_high"]
        attr["water_tank_lifted"] = self.device.details["water_tank_lifted"]
        attr["automatic_stop_reach_target"] = self.device.details[
            "automatic_stop_reach_target"
        ]

        return attr

    def set_mode(self, mode):
        """Set humidifier mode (auto, sleep, manual)."""
        lower_mode = mode.lower()
        if lower_mode not in (self.available_modes):
            raise ValueError(
                f"Invalid mode value: {mode}  Valid values are {', '.join(self.available_modes)}."
            )
        if "manual" in lower_mode:
            level = 3
            manual_mode = lower_mode.split()[1]
            if manual_mode == "low":
                level = 3
            elif manual_mode == "mid":
                level = 6
            else:
                level = 9
            self.device.set_mist_level(level)
        else:
            self.device.set_humidity_mode(lower_mode)

    def set_humidity(self, humidity):
        """Set the humidity level."""
        if not self.is_on:
            self.device.turn_on()
        self.set_mode(MODE_AUTO)
        self.device.set_humidity(humidity)

    def turn_off(self, **kwargs):
        """Set humidifier to off mode."""
        self.device.turn_off()

    def turn_on(self, **kwargs):
        """Set humidifier to on mode."""
        self.device.turn_on()
