"""Support for ZHA valves."""

import functools
from typing import override

from zha.application.platforms.valve.const import (
    ValveEntityFeature as ZHAValveEntityFeature,
)

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHASupportedFeaturesEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation valve from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.VALVE]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZHAValve, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAValve(ZHASupportedFeaturesEntity, ValveEntity):
    """Representation of a ZHA valve."""

    @staticmethod
    @functools.cache
    @override
    def _convert_supported_features(
        zha_features: ZHAValveEntityFeature,
    ) -> ValveEntityFeature:
        """Convert ZHA valve features to HA valve features."""
        features = ValveEntityFeature(0)

        if ZHAValveEntityFeature.OPEN in zha_features:
            features |= ValveEntityFeature.OPEN
        if ZHAValveEntityFeature.CLOSE in zha_features:
            features |= ValveEntityFeature.CLOSE
        if ZHAValveEntityFeature.SET_POSITION in zha_features:
            features |= ValveEntityFeature.SET_POSITION
        if ZHAValveEntityFeature.STOP in zha_features:
            features |= ValveEntityFeature.STOP

        return features

    @override
    def _update_capability_attrs(self) -> None:
        """Re-derive capability attributes from the cached state."""
        super()._update_capability_attrs()

        device_class = self._zha_state.device_class
        self._attr_device_class = (
            ValveDeviceClass(device_class) if device_class is not None else None
        )
        self._attr_reports_position = self._zha_state.reports_position

    @property
    @override
    def current_valve_position(self) -> int | None:
        """Return the current position of the valve."""
        return self._zha_state.current_position

    @property
    @override
    def is_opening(self) -> bool | None:
        """Return if the valve is opening."""
        return self._zha_state.is_opening

    @property
    @override
    def is_closing(self) -> bool | None:
        """Return if the valve is closing."""
        return self._zha_state.is_closing

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        return self._zha_state.is_closed

    @convert_zha_error_to_ha_error()
    @override
    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self.entity_data.entity.async_open_valve()
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self.entity_data.entity.async_close_valve()
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        await self.entity_data.entity.async_set_valve_position(position=position)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_stop_valve(self) -> None:
        """Stop the valve."""
        await self.entity_data.entity.async_stop_valve()
        self.async_write_ha_state()
