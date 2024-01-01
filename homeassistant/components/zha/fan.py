"""Fans on Zigbee Home Automation networks."""
from __future__ import annotations

from abc import abstractmethod
import functools
import math
from typing import Any

from zigpy.zcl.clusters import hvac

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .core import discovery
from .core.cluster_handlers import wrap_zigpy_exceptions
from .core.const import CLUSTER_HANDLER_FAN, SIGNAL_ADD_ENTITIES, SIGNAL_ATTR_UPDATED
from .core.helpers import get_zha_data
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity, ZhaGroupEntity

# Additional speeds in zigbee's ZCL
# Spec is unclear as to what this value means. On King Of Fans HBUniversal
# receiver, this means Very High.
PRESET_MODE_ON = "on"
# The fan speed is self-regulated
PRESET_MODE_AUTO = "auto"
# When the heated/cooled space is occupied, the fan is always on
PRESET_MODE_SMART = "smart"

SPEED_RANGE = (1, 3)  # off is not included
PRESET_MODES_TO_NAME = {4: PRESET_MODE_ON, 5: PRESET_MODE_AUTO, 6: PRESET_MODE_SMART}

DEFAULT_ON_PERCENTAGE = 50

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.FAN)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, Platform.FAN)
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.FAN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation fan from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.FAN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


class BaseFan(FanEntity):
    """Base representation of a ZHA fan."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_translation_key: str = "fan"

    @property
    def preset_modes(self) -> list[str]:
        """Return the available preset modes."""
        return list(self.preset_modes_to_name.values())

    @property
    def preset_modes_to_name(self) -> dict[int, str]:
        """Return a dict from preset mode to name."""
        return PRESET_MODES_TO_NAME

    @property
    def preset_name_to_mode(self) -> dict[str, int]:
        """Return a dict from preset name to mode."""
        return {v: k for k, v in self.preset_modes_to_name.items()}

    @property
    def default_on_percentage(self) -> int:
        """Return the default on percentage."""
        return DEFAULT_ON_PERCENTAGE

    @property
    def speed_range(self) -> tuple[int, int]:
        """Return the range of speeds the fan supports. Off is not included."""
        return SPEED_RANGE

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self.speed_range)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the entity on."""
        if percentage is None:
            percentage = self.default_on_percentage
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        fan_mode = math.ceil(percentage_to_ranged_value(self.speed_range, percentage))
        await self._async_set_fan_mode(fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode for the fan."""
        await self._async_set_fan_mode(self.preset_name_to_mode[preset_mode])

    @abstractmethod
    async def _async_set_fan_mode(self, fan_mode: int) -> None:
        """Set the fan mode for the fan."""

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from cluster handler."""


@STRICT_MATCH(cluster_handler_names=CLUSTER_HANDLER_FAN)
class ZhaFan(BaseFan, ZhaEntity):
    """Representation of a ZHA fan."""

    def __init__(self, unique_id, zha_device, cluster_handlers, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._fan_cluster_handler = self.cluster_handlers.get(CLUSTER_HANDLER_FAN)

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._fan_cluster_handler, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if (
            self._fan_cluster_handler.fan_mode is None
            or self._fan_cluster_handler.fan_mode > self.speed_range[1]
        ):
            return None
        if self._fan_cluster_handler.fan_mode == 0:
            return 0
        return ranged_value_to_percentage(
            self.speed_range, self._fan_cluster_handler.fan_mode
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.preset_modes_to_name.get(self._fan_cluster_handler.fan_mode)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from cluster handler."""
        self.async_write_ha_state()

    async def _async_set_fan_mode(self, fan_mode: int) -> None:
        """Set the fan mode for the fan."""
        await self._fan_cluster_handler.async_set_speed(fan_mode)
        self.async_set_state(0, "fan_mode", fan_mode)


@GROUP_MATCH()
class FanGroup(BaseFan, ZhaGroupEntity):
    """Representation of a fan group."""

    _attr_translation_key: str = "fan_group"

    def __init__(
        self, entity_ids: list[str], unique_id: str, group_id: int, zha_device, **kwargs
    ) -> None:
        """Initialize a fan group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        self._available: bool = False
        group = self.zha_device.gateway.get_group(self._group_id)
        self._fan_cluster_handler = group.endpoint[hvac.Fan.cluster_id]
        self._percentage = None
        self._preset_mode = None

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self._percentage

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._preset_mode

    async def _async_set_fan_mode(self, fan_mode: int) -> None:
        """Set the fan mode for the group."""

        with wrap_zigpy_exceptions():
            await self._fan_cluster_handler.write_attributes({"fan_mode": fan_mode})

        self.async_set_state(0, "fan_mode", fan_mode)

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the fan."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: list[State] = list(filter(None, all_states))
        percentage_states: list[State] = [
            state for state in states if state.attributes.get(ATTR_PERCENTAGE)
        ]
        preset_mode_states: list[State] = [
            state for state in states if state.attributes.get(ATTR_PRESET_MODE)
        ]
        self._available = any(state.state != STATE_UNAVAILABLE for state in states)

        if percentage_states:
            self._percentage = percentage_states[0].attributes[ATTR_PERCENTAGE]
            self._preset_mode = None
        elif preset_mode_states:
            self._preset_mode = preset_mode_states[0].attributes[ATTR_PRESET_MODE]
            self._percentage = None
        else:
            self._percentage = None
            self._preset_mode = None

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await self.async_update()
        await super().async_added_to_hass()


IKEA_SPEED_RANGE = (1, 10)  # off is not included
IKEA_PRESET_MODES_TO_NAME = {
    1: PRESET_MODE_AUTO,
    2: "Speed 1",
    3: "Speed 1.5",
    4: "Speed 2",
    5: "Speed 2.5",
    6: "Speed 3",
    7: "Speed 3.5",
    8: "Speed 4",
    9: "Speed 4.5",
    10: "Speed 5",
}


@MULTI_MATCH(
    cluster_handler_names="ikea_airpurifier",
    models={"STARKVIND Air purifier", "STARKVIND Air purifier table"},
)
class IkeaFan(ZhaFan):
    """Representation of an Ikea fan."""

    def __init__(self, unique_id, zha_device, cluster_handlers, **kwargs) -> None:
        """Init this sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._fan_cluster_handler = self.cluster_handlers.get("ikea_airpurifier")

    @property
    def preset_modes_to_name(self) -> dict[int, str]:
        """Return a dict from preset mode to name."""
        return IKEA_PRESET_MODES_TO_NAME

    @property
    def speed_range(self) -> tuple[int, int]:
        """Return the range of speeds the fan supports. Off is not included."""
        return IKEA_SPEED_RANGE

    @property
    def default_on_percentage(self) -> int:
        """Return the default on percentage."""
        return int(
            (100 / self.speed_count) * self.preset_name_to_mode[PRESET_MODE_AUTO]
        )


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_FAN,
    models={"HBUniversalCFRemote", "HDC52EastwindFan"},
)
class KofFan(ZhaFan):
    """Representation of a fan made by King Of Fans."""

    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

    @property
    def speed_range(self) -> tuple[int, int]:
        """Return the range of speeds the fan supports. Off is not included."""
        return (1, 4)

    @property
    def preset_modes_to_name(self) -> dict[int, str]:
        """Return a dict from preset mode to name."""
        return {6: PRESET_MODE_SMART}
