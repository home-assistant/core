"""Support for Z-Wave cover devices."""
from __future__ import annotations

from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import (
    CURRENT_VALUE_PROPERTY,
    TARGET_STATE_PROPERTY,
    TARGET_VALUE_PROPERTY,
)
from zwave_js_server.const.command_class.barrier_operator import BarrierState
from zwave_js_server.const.command_class.multilevel_switch import (
    COVER_ON_PROPERTY,
    COVER_OPEN_PROPERTY,
    COVER_UP_PROPERTY,
)
from zwave_js_server.const.command_class.window_covering import (
    NO_POSITION_PROPERTY_KEYS,
    NO_POSITION_SUFFIX,
    WINDOW_COVERING_LEVEL_CHANGE_UP_PROPERTY,
    SlatStates,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COVER_POSITION_PROPERTY_KEYS,
    COVER_TILT_PROPERTY_KEYS,
    DATA_CLIENT,
    DOMAIN,
)
from .discovery import ZwaveDiscoveryInfo
from .discovery_data_template import CoverTiltDataTemplate
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave Cover from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_cover(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave cover."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "window_covering":
            entities.append(ZWaveWindowCovering(config_entry, driver, info))
        elif info.platform_hint == "motorized_barrier":
            entities.append(ZwaveMotorizedBarrier(config_entry, driver, info))
        elif info.platform_hint and info.platform_hint.endswith("tilt"):
            entities.append(ZWaveTiltCover(config_entry, driver, info))
        else:
            entities.append(ZWaveMultilevelSwitchCover(config_entry, driver, info))
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{COVER_DOMAIN}",
            async_add_cover,
        )
    )


class CoverPositionMixin(ZWaveBaseEntity, CoverEntity):
    """Mix-in class for cover with position support."""

    _current_position_value: ZwaveValue | None = None
    _target_position_value: ZwaveValue | None = None
    _stop_position_value: ZwaveValue | None = None

    def _set_position_values(
        self,
        current_value: ZwaveValue,
        target_value: ZwaveValue | None = None,
        stop_value: ZwaveValue | None = None,
    ) -> None:
        """Set values for position."""
        self._attr_supported_features = (
            (self._attr_supported_features or 0)
            | CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )
        self._current_position_value = current_value
        self._target_position_value = target_value or self.get_zwave_value(
            TARGET_VALUE_PROPERTY, value_property_key=current_value.property_key
        )

        if stop_value:
            self._stop_position_value = stop_value
            self._attr_supported_features |= CoverEntityFeature.STOP

    def percent_to_zwave_position(self, value: int) -> int:
        """Convert position in 0-100 scale to closed_value-open_value scale."""
        return (
            round(max(min(1, (value / 100)), 0) * self._position_range)
            + self._fully_closed_position
        )

    def zwave_to_percent_position(self, value: int) -> int:
        """Convert closed_value-open_value scale to position in 0-100 scale."""
        return round(
            ((value - self._fully_closed_position) / self._position_range) * 100
        )

    @property
    def _fully_open_position(self) -> int:
        """Return value that represents fully opened position."""
        max_ = self.info.primary_value.metadata.max
        return 99 if max_ is None else max_

    @property
    def _fully_closed_position(self) -> int:
        """Return value that represents fully closed position."""
        min_ = self.info.primary_value.metadata.min
        return 0 if min_ is None else min_

    @property
    def _position_range(self) -> int:
        """Return range between fully opened and fully closed position."""
        return self._fully_open_position - self._fully_closed_position

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        if not (value := self._current_position_value) or value.value is None:
            return None
        return bool(value.value == self._fully_closed_position)

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of cover where 0 means closed and 100 is fully open."""
        if (
            self._current_position_value is None
            or self._current_position_value.value is None
        ):
            # guard missing value
            return None
        return self.zwave_to_percent_position(self._current_position_value.value)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        assert self._target_position_value
        await self._async_set_value(
            self._target_position_value,
            self.percent_to_zwave_position(kwargs[ATTR_POSITION]),
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        assert self._target_position_value
        await self._async_set_value(
            self._target_position_value, self._fully_open_position
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        assert self._target_position_value
        await self._async_set_value(
            self._target_position_value, self._fully_closed_position
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        assert self._stop_position_value
        # Stop the cover, will stop regardless of the actual direction of travel.
        await self._async_set_value(self._stop_position_value, False)


class CoverTiltMixin(ZWaveBaseEntity, CoverEntity):
    """Mix-in class for cover with tilt support."""

    _current_tilt_value: ZwaveValue | None = None
    _target_tilt_value: ZwaveValue | None = None
    _stop_tilt_value: ZwaveValue | None = None

    def _set_tilt_values(
        self,
        current_value: ZwaveValue,
        target_value: ZwaveValue | None = None,
        stop_value: ZwaveValue | None = None,
    ) -> None:
        """Set values for tilt."""
        self._attr_supported_features = (
            (self._attr_supported_features or 0)
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )
        self._current_tilt_value = current_value
        self._target_tilt_value = target_value or self.get_zwave_value(
            TARGET_VALUE_PROPERTY, value_property_key=current_value.property_key
        )

        if stop_value:
            self._stop_tilt_value = stop_value
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT

    def percent_to_zwave_tilt(self, value: int) -> int:
        """Convert position in 0-100 scale to closed_value-open_value scale."""
        return (
            round(max(min(1, (value / 100)), 0) * self._tilt_range)
            + self._fully_closed_tilt
        )

    def zwave_to_percent_tilt(self, value: int) -> int:
        """Convert closed_value-open_value scale to position in 0-100 scale."""
        return round(((value - self._fully_closed_tilt) / self._tilt_range) * 100)

    @property
    def _fully_open_tilt(self) -> int:
        """Return value that represents fully opened tilt."""
        max_ = self.info.primary_value.metadata.max
        return 99 if max_ is None else max_

    @property
    def _fully_closed_tilt(self) -> int:
        """Return value that represents fully closed tilt."""
        min_ = self.info.primary_value.metadata.min
        return 0 if min_ is None else min_

    @property
    def _tilt_range(self) -> int:
        """Return range between fully opened and fully closed tilt."""
        return self._fully_open_tilt - self._fully_closed_tilt

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if (value := self._current_tilt_value) is None or value.value is None:
            return None
        return self.zwave_to_percent_tilt(int(value.value))

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        assert self._target_tilt_value
        await self._async_set_value(
            self._target_tilt_value,
            self.percent_to_zwave_tilt(kwargs[ATTR_TILT_POSITION]),
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        assert self._target_tilt_value
        await self._async_set_value(self._target_tilt_value, self._fully_open_tilt)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        assert self._target_tilt_value
        await self._async_set_value(self._target_tilt_value, self._fully_closed_tilt)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        assert self._stop_tilt_value
        # Stop the tilt, will stop regardless of the actual direction of travel.
        await self._async_set_value(self._stop_tilt_value, False)


class ZWaveMultilevelSwitchCover(CoverPositionMixin):
    """Representation of a Z-Wave Cover that uses Multilevel Switch CC for position."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveCover entity."""
        super().__init__(config_entry, driver, info)
        self._set_position_values(
            self.info.primary_value,
            stop_value=(
                self.get_zwave_value(COVER_OPEN_PROPERTY)
                or self.get_zwave_value(COVER_UP_PROPERTY)
                or self.get_zwave_value(COVER_ON_PROPERTY)
            ),
        )

        # Entity class attributes
        self._attr_device_class = CoverDeviceClass.WINDOW
        if self.info.platform_hint and self.info.platform_hint.startswith("shutter"):
            self._attr_device_class = CoverDeviceClass.SHUTTER
        elif self.info.platform_hint and self.info.platform_hint.startswith("blind"):
            self._attr_device_class = CoverDeviceClass.BLIND
        elif self.info.platform_hint and self.info.platform_hint.startswith("gate"):
            self._attr_device_class = CoverDeviceClass.GATE


class ZWaveTiltCover(ZWaveMultilevelSwitchCover, CoverTiltMixin):
    """Representation of a Z-Wave cover device with tilt."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveCover entity."""
        super().__init__(config_entry, driver, info)

        template = cast(CoverTiltDataTemplate, self.info.platform_data_template)
        self._set_tilt_values(
            template.current_tilt_value(self.info.platform_data),
            template.target_tilt_value(self.info.platform_data),
        )


class ZWaveWindowCovering(CoverPositionMixin, CoverTiltMixin):
    """Representation of a Z-Wave Window Covering cover device."""

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize."""
        super().__init__(config_entry, driver, info)
        pos_value: ZwaveValue | None = None
        tilt_value: ZwaveValue | None = None

        # If primary value is for position, we have to search for a tilt value
        if info.primary_value.property_key in COVER_POSITION_PROPERTY_KEYS:
            pos_value = info.primary_value
            tilt_value = next(
                (
                    value
                    for property_key in COVER_TILT_PROPERTY_KEYS
                    if (
                        value := self.get_zwave_value(
                            CURRENT_VALUE_PROPERTY, value_property_key=property_key
                        )
                    )
                ),
                None,
            )
        # If primary value is for tilt, there is no position value
        else:
            tilt_value = info.primary_value

        # Set position and tilt values if they exist. If the corresponding value is of
        # the type No Position, we remove the corresponding set position feature.
        for set_values_func, value, set_position_feature in (
            (self._set_position_values, pos_value, CoverEntityFeature.SET_POSITION),
            (self._set_tilt_values, tilt_value, CoverEntityFeature.SET_TILT_POSITION),
        ):
            if value:
                set_values_func(
                    value,
                    stop_value=self.get_zwave_value(
                        WINDOW_COVERING_LEVEL_CHANGE_UP_PROPERTY,
                        value_property_key=value.property_key,
                    ),
                )
                if value.property_key in NO_POSITION_PROPERTY_KEYS:
                    assert self._attr_supported_features
                    self._attr_supported_features ^= set_position_feature

        additional_info: list[str] = []
        for value in (self._current_position_value, self._current_tilt_value):
            if value and value.property_key_name:
                additional_info.append(
                    value.property_key_name.removesuffix(f" {NO_POSITION_SUFFIX}")
                )
        self._attr_name = self.generate_name(additional_info=additional_info)
        self._attr_device_class = CoverDeviceClass.WINDOW

    @property
    def _fully_open_tilt(self) -> int:
        """Return position to open cover tilt."""
        return SlatStates.OPEN

    @property
    def _fully_closed_tilt(self) -> int:
        """Return position to close cover tilt."""
        return SlatStates.CLOSED_1

    @property
    def _tilt_range(self) -> int:
        """Return range of valid tilt positions."""
        return abs(SlatStates.CLOSED_2 - SlatStates.CLOSED_1)


class ZwaveMotorizedBarrier(ZWaveBaseEntity, CoverEntity):
    """Representation of a Z-Wave motorized barrier device."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_device_class = CoverDeviceClass.GARAGE

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZwaveMotorizedBarrier entity."""
        super().__init__(config_entry, driver, info)
        # TARGET_STATE_PROPERTY is required in the discovery schema.
        self._target_state = cast(
            ZwaveValue,
            self.get_zwave_value(TARGET_STATE_PROPERTY, add_to_watched_value_ids=False),
        )

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value == BarrierState.OPENING)

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value == BarrierState.CLOSING)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self.info.primary_value.value is None:
            return None
        # If a barrier is in the stopped state, the only way to proceed is by
        # issuing an open cover command. Return None in this case which
        # produces an unknown state and allows it to be resolved with an open
        # command.
        if self.info.primary_value.value == BarrierState.STOPPED:
            return None

        return bool(self.info.primary_value.value == BarrierState.CLOSED)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        await self._async_set_value(self._target_state, BarrierState.OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        await self._async_set_value(self._target_state, BarrierState.CLOSED)
