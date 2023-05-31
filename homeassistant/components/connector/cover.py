"""Support for Motion Blinds using their WLAN API."""

import logging

from connectorlocal.connectorlocal import (
    ONEWAYWIRELESSMODE,
    TWOWAYWIRELESSMODE,
    VENETIANTYPE,
    WIFIMOTORTYPE,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY, MANUFACTURER

HUB_TYPE_DEVICE_CLASS_MAP = {
    1: CoverDeviceClass.SHADE,
    2: CoverDeviceClass.SHUTTER,
    3: CoverDeviceClass.SHADE,
    4: CoverDeviceClass.SHADE,
    6: CoverDeviceClass.SHUTTER,
    7: CoverDeviceClass.GATE,
    8: CoverDeviceClass.AWNING,
    10: CoverDeviceClass.SHADE,
    11: CoverDeviceClass.SHADE,
    12: CoverDeviceClass.CURTAIN,
    13: CoverDeviceClass.CURTAIN,
    14: CoverDeviceClass.CURTAIN,
    26: CoverDeviceClass.SHADE,
    43: CoverDeviceClass.SHUTTER,
}


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Motion Blind from a config entry."""
    entities = []
    connector = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    device_list = await connector.device_list()
    if device_list is None:
        return
    for hub in device_list.values():
        if hub.devicetype in WIFIMOTORTYPE:
            wifi_motor_type = HUB_TYPE_DEVICE_CLASS_MAP.get(
                hub.type, CoverDeviceClass.SHADE
            )
            entities.append(
                TwoWayDevice(
                    coordinator=coordinator,
                    blind=hub,
                    device_class=wifi_motor_type,
                    config_entry=config_entry,
                )
            )
        else:
            for blind in hub.blinds_list.values():
                blind_type = HUB_TYPE_DEVICE_CLASS_MAP.get(
                    blind.type, CoverDeviceClass.SHADE
                )
                if blind.wireless_mode in ONEWAYWIRELESSMODE:
                    entities.append(
                        OneWayDevice(
                            coordinator=coordinator,
                            blind=blind,
                            device_class=blind_type,
                            config_entry=config_entry,
                        )
                    )
                elif blind.wireless_mode in TWOWAYWIRELESSMODE:
                    if blind.type in VENETIANTYPE:
                        entities.append(
                            TiltDevice(
                                coordinator=coordinator,
                                blind=blind,
                                device_class=blind_type,
                                config_entry=config_entry,
                            )
                        )
                    else:
                        entities.append(
                            TwoWayDevice(
                                coordinator=coordinator,
                                blind=blind,
                                device_class=blind_type,
                                config_entry=config_entry,
                            )
                        )
                else:
                    _LOGGER.info("This wirelessMode not support")

    async_add_entities(entities)


class OneWayDevice(CoordinatorEntity, CoverEntity):
    """Representation of a Motion Blind Device."""

    def __init__(self, coordinator, blind, device_class, config_entry):
        """Initialize the blind."""
        super().__init__(coordinator)
        self._blind = blind
        self._attr_device_class = device_class
        self._config_entry = config_entry
        self._attr_name = f"{self._blind.mac[-4:]}"
        self._attr_unique_id = self._blind.mac
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._blind.mac)},
            "manufacturer": MANUFACTURER,
            "name": f"{self._blind.mac[-4:]}",
            "model": "Curtain",
            "via_device": (DOMAIN, self._config_entry.unique_id),
        }

    @property
    def device_class(self):
        """Return the device class."""
        return self._attr_device_class

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return None

    @callback
    def _push_callback(self):
        """Update entity state when a push has been received."""
        self.schedule_update_ha_state(force_refresh=False)

    async def async_added_to_hass(self):
        """Subscribe to multicast pushes."""
        self._blind.register_callback(self._push_callback)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._blind.remove_callback()
        return super().async_will_remove_from_hass()

    @property
    def current_cover_position(self):
        """Return the current position."""
        return None

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.open()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.close()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.stop()


class TwoWayDevice(OneWayDevice):
    """Representation of a Motion Blind Device."""

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._blind.position == 100

    @property
    def current_cover_position(self):
        """Return the current position."""
        return 100 - self._blind.position

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._blind.target_position(100 - position)


class TiltDevice(TwoWayDevice):
    """Representation of a Motion Blind Device."""

    @property
    def current_cover_tilt_position(self):
        """Return current angle of cover."""
        if self._blind.angle is None:
            return None
        return self._blind.angle * 100 / 180

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self._blind.target_angle(180)

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self._blind.target_angle(0)

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        angle = kwargs[ATTR_TILT_POSITION] * 180 / 100
        self._blind.target_angle(angle)

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self._blind.stop()
