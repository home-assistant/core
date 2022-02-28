"""Support for Motion Blinds using their WLAN API."""
import logging

from motionblinds import DEVICE_TYPES_WIFI, BlindType
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_platform,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ABSOLUTE_POSITION,
    ATTR_AVAILABLE,
    ATTR_WIDTH,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GATEWAY,
    KEY_VERSION,
    MANUFACTURER,
    SERVICE_SET_ABSOLUTE_POSITION,
)

_LOGGER = logging.getLogger(__name__)


POSITION_DEVICE_MAP = {
    BlindType.RollerBlind: CoverDeviceClass.SHADE,
    BlindType.RomanBlind: CoverDeviceClass.SHADE,
    BlindType.HoneycombBlind: CoverDeviceClass.SHADE,
    BlindType.DimmingBlind: CoverDeviceClass.SHADE,
    BlindType.DayNightBlind: CoverDeviceClass.SHADE,
    BlindType.RollerShutter: CoverDeviceClass.SHUTTER,
    BlindType.Switch: CoverDeviceClass.SHUTTER,
    BlindType.RollerGate: CoverDeviceClass.GATE,
    BlindType.Awning: CoverDeviceClass.AWNING,
    BlindType.Curtain: CoverDeviceClass.CURTAIN,
    BlindType.CurtainLeft: CoverDeviceClass.CURTAIN,
    BlindType.CurtainRight: CoverDeviceClass.CURTAIN,
}

TILT_DEVICE_MAP = {
    BlindType.VenetianBlind: CoverDeviceClass.BLIND,
    BlindType.ShangriLaBlind: CoverDeviceClass.BLIND,
    BlindType.DoubleRoller: CoverDeviceClass.SHADE,
    BlindType.VerticalBlind: CoverDeviceClass.BLIND,
    BlindType.VerticalBlindLeft: CoverDeviceClass.BLIND,
}

TDBU_DEVICE_MAP = {
    BlindType.TopDownBottomUp: CoverDeviceClass.SHADE,
}


SET_ABSOLUTE_POSITION_SCHEMA = {
    vol.Required(ATTR_ABSOLUTE_POSITION): vol.All(cv.positive_int, vol.Range(max=100)),
    vol.Optional(ATTR_WIDTH): vol.All(cv.positive_int, vol.Range(max=100)),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Motion Blind from a config entry."""
    entities = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    sw_version = hass.data[DOMAIN][config_entry.entry_id][KEY_VERSION]

    for blind in motion_gateway.device_list.values():
        if blind.type in POSITION_DEVICE_MAP:
            entities.append(
                MotionPositionDevice(
                    coordinator,
                    blind,
                    POSITION_DEVICE_MAP[blind.type],
                    config_entry,
                    sw_version,
                )
            )

        elif blind.type in TILT_DEVICE_MAP:
            entities.append(
                MotionTiltDevice(
                    coordinator,
                    blind,
                    TILT_DEVICE_MAP[blind.type],
                    config_entry,
                    sw_version,
                )
            )

        elif blind.type in TDBU_DEVICE_MAP:
            entities.append(
                MotionTDBUDevice(
                    coordinator,
                    blind,
                    TDBU_DEVICE_MAP[blind.type],
                    config_entry,
                    sw_version,
                    "Top",
                )
            )
            entities.append(
                MotionTDBUDevice(
                    coordinator,
                    blind,
                    TDBU_DEVICE_MAP[blind.type],
                    config_entry,
                    sw_version,
                    "Bottom",
                )
            )
            entities.append(
                MotionTDBUDevice(
                    coordinator,
                    blind,
                    TDBU_DEVICE_MAP[blind.type],
                    config_entry,
                    sw_version,
                    "Combined",
                )
            )

        else:
            _LOGGER.warning(
                "Blind type '%s' not yet supported, " "assuming RollerBlind",
                blind.blind_type,
            )
            entities.append(
                MotionPositionDevice(
                    coordinator,
                    blind,
                    POSITION_DEVICE_MAP[BlindType.RollerBlind],
                    config_entry,
                    sw_version,
                )
            )

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_ABSOLUTE_POSITION,
        SET_ABSOLUTE_POSITION_SCHEMA,
        SERVICE_SET_ABSOLUTE_POSITION,
    )


class MotionPositionDevice(CoordinatorEntity, CoverEntity):
    """Representation of a Motion Blind Device."""

    def __init__(self, coordinator, blind, device_class, config_entry, sw_version):
        """Initialize the blind."""
        super().__init__(coordinator)

        self._blind = blind
        self._config_entry = config_entry

        if blind.device_type in DEVICE_TYPES_WIFI:
            via_device = ()
            connections = {(dr.CONNECTION_NETWORK_MAC, blind.mac)}
            name = blind.blind_type
        else:
            via_device = (DOMAIN, blind._gateway.mac)
            connections = {}
            name = f"{blind.blind_type}-{blind.mac[12:]}"
            sw_version = None

        self._attr_device_class = device_class
        self._attr_name = name
        self._attr_unique_id = blind.mac
        self._attr_device_info = DeviceInfo(
            connections=connections,
            identifiers={(DOMAIN, blind.mac)},
            manufacturer=MANUFACTURER,
            model=blind.blind_type,
            name=name,
            via_device=via_device,
            sw_version=sw_version,
            hw_version=blind.wireless_name,
        )

    @property
    def available(self):
        """Return True if entity is available."""
        if self.coordinator.data is None:
            return False

        if not self.coordinator.data[KEY_GATEWAY][ATTR_AVAILABLE]:
            return False

        return self.coordinator.data[self._blind.mac][ATTR_AVAILABLE]

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.position is None:
            return None
        return 100 - self._blind.position

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None
        return self._blind.position == 100

    async def async_added_to_hass(self):
        """Subscribe to multicast pushes and register signal handler."""
        self._blind.Register_callback(self.unique_id, self.schedule_update_ha_state)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._blind.Remove_callback(self.unique_id)
        await super().async_will_remove_from_hass()

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._blind.Set_position(100 - position)

    def set_absolute_position(self, **kwargs):
        """Move the cover to a specific absolute position (see TDBU)."""
        position = kwargs[ATTR_ABSOLUTE_POSITION]
        self._blind.Set_position(100 - position)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()


class MotionTiltDevice(MotionPositionDevice):
    """Representation of a Motion Blind Device."""

    @property
    def current_cover_tilt_position(self):
        """
        Return current angle of cover.

        None is unknown, 0 is closed/minimum tilt, 100 is fully open/maximum tilt.
        """
        if self._blind.angle is None:
            return None
        return self._blind.angle * 100 / 180

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self._blind.Set_angle(180)

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self._blind.Set_angle(0)

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        angle = kwargs[ATTR_TILT_POSITION] * 180 / 100
        self._blind.Set_angle(angle)

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()


class MotionTDBUDevice(MotionPositionDevice):
    """Representation of a Motion Top Down Bottom Up blind Device."""

    def __init__(
        self, coordinator, blind, device_class, config_entry, sw_version, motor
    ):
        """Initialize the blind."""
        super().__init__(coordinator, blind, device_class, config_entry, sw_version)
        self._motor = motor
        self._motor_key = motor[0]
        self._attr_name = f"{blind.blind_type}-{motor}-{blind.mac[12:]}"
        self._attr_unique_id = f"{blind.mac}-{motor}"

        if self._motor not in ["Bottom", "Top", "Combined"]:
            _LOGGER.error("Unknown motor '%s'", self._motor)

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.scaled_position is None:
            return None

        return 100 - self._blind.scaled_position[self._motor_key]

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None

        if self._motor == "Combined":
            return self._blind.width == 100

        return self._blind.position[self._motor_key] == 100

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if self._blind.position is not None:
            attributes[ATTR_ABSOLUTE_POSITION] = (
                100 - self._blind.position[self._motor_key]
            )
        if self._blind.width is not None:
            attributes[ATTR_WIDTH] = self._blind.width
        return attributes

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open(motor=self._motor_key)

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close(motor=self._motor_key)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific scaled position."""
        position = kwargs[ATTR_POSITION]
        self._blind.Set_scaled_position(100 - position, motor=self._motor_key)

    def set_absolute_position(self, **kwargs):
        """Move the cover to a specific absolute position."""
        position = kwargs[ATTR_ABSOLUTE_POSITION]
        target_width = kwargs.get(ATTR_WIDTH, None)

        self._blind.Set_position(
            100 - position, motor=self._motor_key, width=target_width
        )

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop(motor=self._motor_key)
