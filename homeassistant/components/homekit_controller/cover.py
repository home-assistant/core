"""Support for Homekit covers."""

from __future__ import annotations

from functools import cached_property
from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import HomeKitEntity

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit covers."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if not (entity_class := ENTITY_TYPES.get(service.type)):
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        entity: HomeKitEntity = entity_class(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.COVER
        )
        async_add_entities([entity])
        return True

    conn.add_listener(async_add_service)


class HomeKitGarageDoorCover(HomeKitEntity, CoverEntity):
    """Representation of a HomeKit Garage Door."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.DOOR_STATE_CURRENT,
            CharacteristicsTypes.DOOR_STATE_TARGET,
            CharacteristicsTypes.OBSTRUCTION_DETECTED,
        ]

    @property
    def _state(self) -> str:
        """Return the current state of the garage door."""
        value = self.service.value(CharacteristicsTypes.DOOR_STATE_CURRENT)
        return CURRENT_GARAGE_STATE_MAP[value]

    @property
    def is_closed(self) -> bool:
        """Return true if cover is closed, else False."""
        return self._state == STATE_CLOSED

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._state == STATE_CLOSING

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._state == STATE_OPENING

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send open command."""
        await self.set_door_state(STATE_OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send close command."""
        await self.set_door_state(STATE_CLOSED)

    async def set_door_state(self, state: str) -> None:
        """Send state command."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.DOOR_STATE_TARGET: TARGET_GARAGE_STATE_MAP[state]}
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        obstruction_detected = self.service.value(
            CharacteristicsTypes.OBSTRUCTION_DETECTED
        )
        return {"obstruction-detected": obstruction_detected is True}


class HomeKitWindowCover(HomeKitEntity, CoverEntity):
    """Representation of a HomeKit Window or Window Covering."""

    @callback
    def _async_reconfigure(self) -> None:
        """Reconfigure entity."""
        self._async_clear_property_cache(("supported_features",))
        super()._async_reconfigure()

    def get_characteristic_types(self) -> list[str]:
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

    @cached_property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )

        if self.service.has(CharacteristicsTypes.POSITION_HOLD):
            features |= CoverEntityFeature.STOP

        if self.service.has(
            CharacteristicsTypes.VERTICAL_TILT_CURRENT
        ) or self.service.has(CharacteristicsTypes.HORIZONTAL_TILT_CURRENT):
            features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

        return features

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        return self.service.value(CharacteristicsTypes.POSITION_CURRENT)

    @property
    def is_closed(self) -> bool:
        """Return true if cover is closed, else False."""
        return self.current_cover_position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        value = self.service.value(CharacteristicsTypes.POSITION_STATE)
        state = CURRENT_WINDOW_STATE_MAP[value]
        return state == STATE_CLOSING

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        value = self.service.value(CharacteristicsTypes.POSITION_STATE)
        state = CURRENT_WINDOW_STATE_MAP[value]
        return state == STATE_OPENING

    @property
    def is_horizontal_tilt(self) -> bool:
        """Return True if the service has a horizontal tilt characteristic."""
        return (
            self.service.value(CharacteristicsTypes.HORIZONTAL_TILT_CURRENT) is not None
        )

    @property
    def is_vertical_tilt(self) -> bool:
        """Return True if the service has a vertical tilt characteristic."""
        return (
            self.service.value(CharacteristicsTypes.VERTICAL_TILT_CURRENT) is not None
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""
        tilt_position = self.service.value(CharacteristicsTypes.VERTICAL_TILT_CURRENT)
        if not tilt_position:
            tilt_position = self.service.value(
                CharacteristicsTypes.HORIZONTAL_TILT_CURRENT
            )
        if tilt_position is None:
            return None
        # Recalculate to convert from arcdegree scale to percentage scale.
        if self.is_vertical_tilt:
            scale = 0.9
            if (
                self.service[CharacteristicsTypes.VERTICAL_TILT_CURRENT].minValue == -90
                and self.service[CharacteristicsTypes.VERTICAL_TILT_CURRENT].maxValue
                == 0
            ):
                scale = -0.9
            tilt_position = int(tilt_position / scale)
        elif self.is_horizontal_tilt:
            scale = 0.9
            if (
                self.service[CharacteristicsTypes.HORIZONTAL_TILT_TARGET].minValue
                == -90
                and self.service[CharacteristicsTypes.HORIZONTAL_TILT_TARGET].maxValue
                == 0
            ):
                scale = -0.9
            tilt_position = int(tilt_position / scale)
        return tilt_position

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Send hold command."""
        await self.async_put_characteristics({CharacteristicsTypes.POSITION_HOLD: 1})

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send open command."""
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send close command."""
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Send position command."""
        position = kwargs[ATTR_POSITION]
        await self.async_put_characteristics(
            {CharacteristicsTypes.POSITION_TARGET: position}
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        if self.is_vertical_tilt:
            # Recalculate to convert from percentage scale to arcdegree scale.
            scale = 0.9
            if (
                self.service[CharacteristicsTypes.VERTICAL_TILT_TARGET].minValue == -90
                and self.service[CharacteristicsTypes.VERTICAL_TILT_TARGET].maxValue
                == 0
            ):
                scale = -0.9
            tilt_position = int(tilt_position * scale)
            await self.async_put_characteristics(
                {CharacteristicsTypes.VERTICAL_TILT_TARGET: tilt_position}
            )
        elif self.is_horizontal_tilt:
            # Recalculate to convert from percentage scale to arcdegree scale.
            scale = 0.9
            if (
                self.service[CharacteristicsTypes.HORIZONTAL_TILT_TARGET].minValue
                == -90
                and self.service[CharacteristicsTypes.HORIZONTAL_TILT_TARGET].maxValue
                == 0
            ):
                scale = -0.9
            tilt_position = int(tilt_position * scale)
            await self.async_put_characteristics(
                {CharacteristicsTypes.HORIZONTAL_TILT_TARGET: tilt_position}
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        obstruction_detected = self.service.value(
            CharacteristicsTypes.OBSTRUCTION_DETECTED
        )
        if not obstruction_detected:
            return {}
        return {"obstruction-detected": obstruction_detected}


class HomeKitWindow(HomeKitWindowCover):
    """Representation of a HomeKit Window."""

    _attr_device_class = CoverDeviceClass.WINDOW


ENTITY_TYPES = {
    ServicesTypes.GARAGE_DOOR_OPENER: HomeKitGarageDoorCover,
    ServicesTypes.WINDOW_COVERING: HomeKitWindowCover,
    ServicesTypes.WINDOW: HomeKitWindow,
}
