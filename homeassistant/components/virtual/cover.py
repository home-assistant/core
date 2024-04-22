"""Provide support for a virtual cover."""

import asyncio
from datetime import timedelta
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as PLATFORM_DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.rasc.helpers import Dataset, load_dataset
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_CLOSED
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_entity_configs
from .const import (
    ATTR_GROUP_NAME,
    COMPONENT_DOMAIN,
    COMPONENT_NETWORK,
    CONF_CLASS,
    CONF_COORDINATED,
    CONF_INITIAL_VALUE,
    CONF_SIMULATE_NETWORK,
)
from .coordinator import VirtualDataUpdateCoordinator
from .entity import CoordinatedVirtualEntity, VirtualEntity, virtual_schema
from .network import NetworkProxy

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [COMPONENT_DOMAIN]

CONF_CHANGE_TIME = "opening_time"

DEFAULT_COVER_VALUE = "open"
DEFAULT_CHANGE_TIME = timedelta(seconds=0)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    virtual_schema(
        DEFAULT_COVER_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
            vol.Optional(CONF_CHANGE_TIME, default=DEFAULT_CHANGE_TIME): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
        },
    )
)
COVER_SCHEMA = vol.Schema(
    virtual_schema(
        DEFAULT_COVER_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
            vol.Optional(CONF_CHANGE_TIME, default=DEFAULT_CHANGE_TIME): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
        },
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up covers."""

    coordinator: VirtualDataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][
        entry.entry_id
    ]
    entities: list[VirtualCover] = []
    for entity_config in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity_config = COVER_SCHEMA(entity_config)
        if entity_config[CONF_COORDINATED]:
            entity = cast(
                VirtualCover, CoordinatedVirtualCover(entity_config, coordinator)
            )
        else:
            entity = VirtualCover(entity_config)

        if entity_config[CONF_SIMULATE_NETWORK]:
            entity = cast(VirtualCover, NetworkProxy(entity))
            hass.data[COMPONENT_NETWORK][entity.entity_id] = entity

        entities.append(entity)

    async_add_entities(entities)


class VirtualCover(VirtualEntity, CoverEntity):
    """Representation of a Virtual cover."""

    def __init__(self, config):
        """Initialize the Virtual cover device."""
        super().__init__(config, PLATFORM_DOMAIN)

        self._attr_device_class = config.get(CONF_CLASS, CoverDeviceClass.SHADE)
        if self._attr_device_class == CoverDeviceClass.DOOR:
            self._dataset = load_dataset(Dataset.DOOR)
        self._attr_supported_features = CoverEntityFeature(
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )

        if self._attr_device_class in [
            CoverDeviceClass.AWNING,
            CoverDeviceClass.BLIND,
            CoverDeviceClass.CURTAIN,
            CoverDeviceClass.SHADE,
        ]:
            self._attr_supported_features |= CoverEntityFeature(
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
                | CoverEntityFeature.STOP_TILT
            )

        self._change_time: timedelta = config.get(CONF_CHANGE_TIME)

        # cancel transition
        self.cover_tasks: set[asyncio.Task] = set()
        self.tilt_tasks = set()

    def _create_state(self, config):
        super()._create_state(config)

        self._attr_is_closed = config.get(CONF_INITIAL_VALUE).lower() == STATE_CLOSED
        self._attr_current_cover_position = 0 if self._attr_is_closed else 100

    def _restore_state(self, state, config):
        super()._restore_state(state, config)

        self._attr_is_closed = state.state.lower() == STATE_CLOSED
        self._attr_current_cover_position = 0 if self._attr_is_closed else 100

    def _update_attributes(self):
        super()._update_attributes()
        self._attr_extra_state_attributes.update(
            {
                name: value
                for name, value in (
                    (ATTR_DEVICE_CLASS, self._attr_device_class),
                    (ATTR_CURRENT_POSITION, self._attr_current_cover_position),
                    (
                        ATTR_CURRENT_TILT_POSITION,
                        self._attr_current_cover_tilt_position,
                    ),
                )
                if value is not None
            }
        )

    def _opening(self) -> None:
        self._attr_is_opening = True
        self._attr_is_closing = False
        self._attr_is_closed = False
        self._update_attributes()

    def _closing(self) -> None:
        self._attr_is_opening = False
        self._attr_is_closing = True
        self._attr_is_closed = False
        self._update_attributes()

    def _close_cover(self) -> None:
        self._attr_current_cover_position = 0
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_is_closed = True
        self._update_attributes()

    def _open_cover(self) -> None:
        self._attr_current_cover_position = 100
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_is_closed = False
        self._update_attributes()

    async def _start_operation(self):
        try:
            if self.is_opening:
                target_position = 100.0
            elif self.is_closing:
                target_position = 0.0
            step = (
                target_position - self._attr_current_cover_position
            ) / self._change_time.total_seconds()
            while True:
                self._attr_current_cover_position += step
                if self._attr_current_cover_position >= 100:
                    self._attr_current_cover_position = 100
                    self._open_cover()
                    break
                if self._attr_current_cover_position <= 0:
                    self._attr_current_cover_position = 0
                    self._close_cover()
                    break
                self._update_attributes()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            if self._attr_current_cover_position >= 100:
                self._attr_current_cover_position = 100
                self._open_cover()
            elif self._attr_current_cover_position <= 0:
                self._attr_current_cover_position = 0
                self._close_cover()
            self._update_attributes()

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._change_time == DEFAULT_CHANGE_TIME:
            self._open_cover()
        else:
            self._opening()
            task = self.hass.async_create_task(self._start_operation())
            self.cover_tasks.add(task)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._change_time == DEFAULT_CHANGE_TIME:
            self._close_cover()
        else:
            self._closing()
            task = self.hass.async_create_task(self._start_operation())
            self.cover_tasks.add(task)

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        for task in self.cover_tasks:
            task.cancel()
        self.cover_tasks.clear()

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        self._attr_current_cover_tilt_position = 100
        self._update_attributes()

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        self._attr_current_cover_tilt_position = 0
        self._update_attributes()

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self._attr_current_cover_position = kwargs[ATTR_POSITION]
        self._update_attributes()

    def stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""
        raise NotImplementedError()

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        self._attr_current_cover_tilt_position = kwargs[ATTR_TILT_POSITION]
        self._update_attributes()


class CoordinatedVirtualCover(CoordinatedVirtualEntity, VirtualCover):
    """Representation of a Virtual switch."""

    def __init__(self, config, coordinator):
        """Initialize the Virtual switch device."""
        CoordinatedVirtualEntity.__init__(self, coordinator)
        VirtualCover.__init__(self, config)
