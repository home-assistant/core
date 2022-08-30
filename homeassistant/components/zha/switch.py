"""Switches on Zigbee Home Automation networks."""
from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any, TypeVar

import zigpy.exceptions
from zigpy.zcl.clusters.general import OnOff
from zigpy.zcl.foundation import Status

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CHANNEL_ON_OFF,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity, ZhaGroupEntity

if TYPE_CHECKING:
    from .core.channels.base import ZigbeeChannel
    from .core.device import ZHADevice

_ZHASwitchConfigurationEntitySelfT = TypeVar(
    "_ZHASwitchConfigurationEntitySelfT", bound="ZHASwitchConfigurationEntity"
)

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.SWITCH)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, Platform.SWITCH)
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.SWITCH
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation switch from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.SWITCH]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF)
class Switch(ZhaEntity, SwitchEntity):
    """ZHA switch."""

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> None:
        """Initialize the ZHA switch."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._on_off_channel = self.cluster_channels[CHANNEL_ON_OFF]

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._on_off_channel.on_off is None:
            return False
        return self._on_off_channel.on_off

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        result = await self._on_off_channel.turn_on()
        if not result:
            return
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        result = await self._on_off_channel.turn_off()
        if not result:
            return
        self.async_write_ha_state()

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any):
        """Handle state update from channel."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._on_off_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the switch."""
        await super().async_update()
        if self._on_off_channel:
            await self._on_off_channel.get_attribute_value("on_off", from_cache=False)


@GROUP_MATCH()
class SwitchGroup(ZhaGroupEntity, SwitchEntity):
    """Representation of a switch group."""

    def __init__(
        self,
        entity_ids: list[str],
        unique_id: str,
        group_id: int,
        zha_device: ZHADevice,
        **kwargs: Any,
    ) -> None:
        """Initialize a switch group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        self._available: bool
        self._state: bool
        group = self.zha_device.gateway.get_group(self._group_id)
        self._on_off_channel = group.endpoint[OnOff.cluster_id]

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        return bool(self._state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        result = await self._on_off_channel.on()
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        result = await self._on_off_channel.off()
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return
        self._state = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Query all members and determine the light group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: list[State] = list(filter(None, all_states))
        on_states = [state for state in states if state.state == STATE_ON]

        self._state = len(on_states) > 0
        self._available = any(state.state != STATE_UNAVAILABLE for state in states)


class ZHASwitchConfigurationEntity(ZhaEntity, SwitchEntity):
    """Representation of a ZHA switch configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _zcl_attribute: str
    _zcl_inverter_attribute: str = ""

    @classmethod
    def create_entity(
        cls: type[_ZHASwitchConfigurationEntitySelfT],
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> _ZHASwitchConfigurationEntitySelfT | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        channel = channels[0]
        if (
            cls._zcl_attribute in channel.cluster.unsupported_attributes
            or channel.cluster.get(cls._zcl_attribute) is None
        ):
            _LOGGER.debug(
                "%s is not supported - skipping %s entity creation",
                cls._zcl_attribute,
                cls.__name__,
            )
            return None

        return cls(unique_id, zha_device, channels, **kwargs)

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> None:
        """Init this number configuration entity."""
        self._channel: ZigbeeChannel = channels[0]
        super().__init__(unique_id, zha_device, channels, **kwargs)

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any):
        """Handle state update from channel."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        val = bool(self._channel.cluster.get(self._zcl_attribute))
        invert = bool(self._channel.cluster.get(self._zcl_inverter_attribute))
        return (not val) if invert else val

    async def async_turn_on_off(self, state: bool) -> None:
        """Turn the entity on or off."""
        try:
            invert = bool(self._channel.cluster.get(self._zcl_inverter_attribute))
            result = await self._channel.cluster.write_attributes(
                {self._zcl_attribute: not state if invert else state}
            )
        except zigpy.exceptions.ZigbeeException as ex:
            self.error("Could not set value: %s", ex)
            return
        if not isinstance(result, Exception) and all(
            record.status == Status.SUCCESS for record in result[0]
        ):
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.async_turn_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.async_turn_on_off(False)

    async def async_update(self) -> None:
        """Attempt to retrieve the state of the entity."""
        await super().async_update()
        _LOGGER.error("Polling current state")
        if self._channel:
            value = await self._channel.get_attribute_value(
                self._zcl_attribute, from_cache=False
            )
            invert = await self._channel.get_attribute_value(
                self._zcl_inverter_attribute, from_cache=False
            )
            _LOGGER.debug("read value=%s, inverter=%s", value, bool(invert))


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_b6wax7g0",
    },
)
class OnOffWindowDetectionFunctionConfigurationEntity(
    ZHASwitchConfigurationEntity, id_suffix="on_off_window_opened_detection"
):
    """Representation of a ZHA window detection configuration entity."""

    _zcl_attribute: str = "window_detection_function"
    _zcl_inverter_attribute: str = "window_detection_function_inverter"


@CONFIG_DIAGNOSTIC_MATCH(channel_names="opple_cluster", models={"lumi.motion.ac02"})
class P1MotionTriggerIndicatorSwitch(
    ZHASwitchConfigurationEntity, id_suffix="trigger_indicator"
):
    """Representation of a ZHA motion triggering configuration entity."""

    _zcl_attribute: str = "trigger_indicator"


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="ikea_airpurifier",
    models={"STARKVIND Air purifier", "STARKVIND Air purifier table"},
)
class ChildLock(ZHASwitchConfigurationEntity, id_suffix="child_lock"):
    """ZHA BinarySensor."""

    _zcl_attribute: str = "child_lock"


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="ikea_airpurifier",
    models={"STARKVIND Air purifier", "STARKVIND Air purifier table"},
)
class DisableLed(ZHASwitchConfigurationEntity, id_suffix="disable_led"):
    """ZHA BinarySensor."""

    _zcl_attribute: str = "disable_led"
