"""Support for Homekit covers."""
from aiohomekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

STATE_STOPPED = "stopped"

CURRENT_GARAGE_STATE_MAP = {
    0: STATE_OPEN,
    1: STATE_CLOSED,
    2: STATE_OPENING,
    3: STATE_CLOSING,
    4: STATE_STOPPED,
}

TARGET_GARAGE_STATE_MAP = {STATE_OPEN: 0, STATE_CLOSED: 1, STATE_STOPPED: 2}

CURRENT_WINDOW_STATE_MAP = {0: STATE_CLOSING, 1: STATE_OPENING, 2: STATE_STOPPED}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit covers."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        info = {"aid": aid, "iid": service["iid"]}
        if service["stype"] == "garage-door-opener":
            async_add_entities([HomeKitGarageDoorCover(conn, info)], True)
            return True

        if service["stype"] in ("window-covering", "window"):
            async_add_entities([HomeKitWindowCover(conn, info)], True)
            return True

        return False

    conn.add_listener(async_add_service)


class HomeKitGarageDoorCover(HomeKitEntity, CoverEntity):
    """Representation of a HomeKit Garage Door."""

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return "garage"

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.DOOR_STATE_CURRENT,
            CharacteristicsTypes.DOOR_STATE_TARGET,
            CharacteristicsTypes.OBSTRUCTION_DETECTED,
        ]

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def state(self):
        """Return the current state of the garage door."""
        value = self.service.value(CharacteristicsTypes.DOOR_STATE_CURRENT)
        return CURRENT_GARAGE_STATE_MAP[value]

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self.state == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self.state == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self.state == STATE_OPENING

    async def async_open_cover(self, **kwargs):
        """Send open command."""
        await self.set_door_state(STATE_OPEN)

    async def async_close_cover(self, **kwargs):
        """Send close command."""
        await self.set_door_state(STATE_CLOSED)

    async def set_door_state(self, state):
        """Send state command."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.DOOR_STATE_TARGET: TARGET_GARAGE_STATE_MAP[state]}
        )

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        obstruction_detected = self.service.value(
            CharacteristicsTypes.OBSTRUCTION_DETECTED
        )
        return {"obstruction-detected": obstruction_detected is True}


class HomeKitWindowCover(HomeKitEntity, CoverEntity):
    """Representation of a HomeKit Window or Window Covering."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.POSITION_STATE,
            CharacteristicsTypes.POSITION_CURRENT,
            CharacteristicsTypes.POSITION_TARGET,
            CharacteristicsTypes.POSITION_HOLD,
            CharacteristicsTypes.VERTICAL_TILT_CURRENT,
            CharacteristicsTypes.VERTICAL_TILT_TARGET,
            CharacteristicsTypes.HORIZONTAL_TILT_CURRENT,
            CharacteristicsTypes.HORIZONTAL_TILT_TARGET,
            CharacteristicsTypes.OBSTRUCTION_DETECTED,
        ]

    @property
    def supported_features(self):
        """Flag supported features."""
        features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

        if self.service.has(CharacteristicsTypes.POSITION_HOLD):
            features |= SUPPORT_STOP

        supports_tilt = any(
            (
                self.service.has(CharacteristicsTypes.VERTICAL_TILT_CURRENT),
                self.service.has(CharacteristicsTypes.HORIZONTAL_TILT_CURRENT),
            )
        )

        if supports_tilt:
            features |= (
                SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_SET_TILT_POSITION
            )

        return features

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self.service.value(CharacteristicsTypes.POSITION_CURRENT)

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self.current_cover_position == 0

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        value = self.service.value(CharacteristicsTypes.POSITION_STATE)
        state = CURRENT_WINDOW_STATE_MAP[value]
        return state == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        value = self.service.value(CharacteristicsTypes.POSITION_STATE)
        state = CURRENT_WINDOW_STATE_MAP[value]
        return state == STATE_OPENING

    @property
    def is_horizontal_tilt(self):
        """Return True if the service has a horizontal tilt characteristic."""
        return (
            self.service.value(CharacteristicsTypes.HORIZONTAL_TILT_CURRENT) is not None
        )

    @property
    def is_vertical_tilt(self):
        """Return True if the service has a vertical tilt characteristic."""
        return (
            self.service.value(CharacteristicsTypes.VERTICAL_TILT_CURRENT) is not None
        )

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        tilt_position = self.service.value(CharacteristicsTypes.VERTICAL_TILT_CURRENT)
        if not tilt_position:
            tilt_position = self.service.value(
                CharacteristicsTypes.HORIZONTAL_TILT_CURRENT
            )
        return tilt_position

    async def async_stop_cover(self, **kwargs):
        """Send hold command."""
        await self.async_put_characteristics({CharacteristicsTypes.POSITION_HOLD: 1})

    async def async_open_cover(self, **kwargs):
        """Send open command."""
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs):
        """Send close command."""
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs):
        """Send position command."""
        position = kwargs[ATTR_POSITION]
        await self.async_put_characteristics(
            {CharacteristicsTypes.POSITION_TARGET: position}
        )

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        if self.is_vertical_tilt:
            await self.async_put_characteristics(
                {CharacteristicsTypes.VERTICAL_TILT_TARGET: tilt_position}
            )
        elif self.is_horizontal_tilt:
            await self.async_put_characteristics(
                {CharacteristicsTypes.HORIZONTAL_TILT_TARGET: tilt_position}
            )

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        obstruction_detected = self.service.value(
            CharacteristicsTypes.OBSTRUCTION_DETECTED
        )
        if not obstruction_detected:
            return {}
        return {"obstruction-detected": obstruction_detected}
