"""
Mapping registries for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import collections
from typing import Callable, Set, Union

import attr
import bellows.ezsp
import bellows.zigbee.application
import zigpy.profiles.zha
import zigpy.profiles.zll
import zigpy.zcl as zcl
import zigpy_cc.api
import zigpy_cc.zigbee.application
import zigpy_deconz.api
import zigpy_deconz.zigbee.application
import zigpy_xbee.api
import zigpy_xbee.zigbee.application
import zigpy_zigate.api
import zigpy_zigate.zigbee.application

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH

# importing channels updates registries
from . import channels  # noqa: F401 pylint: disable=unused-import
from .const import CONTROLLER, ZHA_GW_RADIO, ZHA_GW_RADIO_DESCRIPTION, RadioType
from .decorators import CALLABLE_T, DictRegistry, SetRegistry

SMARTTHINGS_ACCELERATION_CLUSTER = 0xFC02
SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE = 0x8000
SMARTTHINGS_HUMIDITY_CLUSTER = 0xFC45

REMOTE_DEVICE_TYPES = {
    zigpy.profiles.zha.PROFILE_ID: [
        zigpy.profiles.zha.DeviceType.COLOR_CONTROLLER,
        zigpy.profiles.zha.DeviceType.COLOR_DIMMER_SWITCH,
        zigpy.profiles.zha.DeviceType.COLOR_SCENE_CONTROLLER,
        zigpy.profiles.zha.DeviceType.DIMMER_SWITCH,
        zigpy.profiles.zha.DeviceType.LEVEL_CONTROL_SWITCH,
        zigpy.profiles.zha.DeviceType.NON_COLOR_CONTROLLER,
        zigpy.profiles.zha.DeviceType.NON_COLOR_SCENE_CONTROLLER,
        zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
        zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT_SWITCH,
        zigpy.profiles.zha.DeviceType.REMOTE_CONTROL,
        zigpy.profiles.zha.DeviceType.SCENE_SELECTOR,
    ],
    zigpy.profiles.zll.PROFILE_ID: [
        zigpy.profiles.zll.DeviceType.COLOR_CONTROLLER,
        zigpy.profiles.zll.DeviceType.COLOR_SCENE_CONTROLLER,
        zigpy.profiles.zll.DeviceType.CONTROL_BRIDGE,
        zigpy.profiles.zll.DeviceType.CONTROLLER,
        zigpy.profiles.zll.DeviceType.SCENE_CONTROLLER,
    ],
}

SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {
    # this works for now but if we hit conflicts we can break it out to
    # a different dict that is keyed by manufacturer
    SMARTTHINGS_ACCELERATION_CLUSTER: BINARY_SENSOR,
    SMARTTHINGS_HUMIDITY_CLUSTER: SENSOR,
    zcl.clusters.closures.DoorLock: LOCK,
    zcl.clusters.closures.WindowCovering: COVER,
    zcl.clusters.general.AnalogInput.cluster_id: SENSOR,
    zcl.clusters.general.MultistateInput.cluster_id: SENSOR,
    zcl.clusters.general.OnOff: SWITCH,
    zcl.clusters.general.PowerConfiguration: SENSOR,
    zcl.clusters.homeautomation.ElectricalMeasurement: SENSOR,
    zcl.clusters.hvac.Fan: FAN,
    zcl.clusters.measurement.IlluminanceMeasurement: SENSOR,
    zcl.clusters.measurement.OccupancySensing: BINARY_SENSOR,
    zcl.clusters.measurement.PressureMeasurement: SENSOR,
    zcl.clusters.measurement.RelativeHumidity: SENSOR,
    zcl.clusters.measurement.TemperatureMeasurement: SENSOR,
    zcl.clusters.security.IasZone: BINARY_SENSOR,
    zcl.clusters.smartenergy.Metering: SENSOR,
}

SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {zcl.clusters.general.OnOff: BINARY_SENSOR}

SWITCH_CLUSTERS = SetRegistry()

BINARY_SENSOR_CLUSTERS = SetRegistry()
BINARY_SENSOR_CLUSTERS.add(SMARTTHINGS_ACCELERATION_CLUSTER)

BINDABLE_CLUSTERS = SetRegistry()
CHANNEL_ONLY_CLUSTERS = SetRegistry()
CLUSTER_REPORT_CONFIGS = {}
CUSTOM_CLUSTER_MAPPINGS = {}

DEVICE_CLASS = {
    zigpy.profiles.zha.PROFILE_ID: {
        SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE: DEVICE_TRACKER,
        zigpy.profiles.zha.DeviceType.COLOR_DIMMABLE_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_BALLAST: LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_PLUG_IN_UNIT: LIGHT,
        zigpy.profiles.zha.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT: LIGHT,
        zigpy.profiles.zha.DeviceType.ON_OFF_BALLAST: SWITCH,
        zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT: LIGHT,
        zigpy.profiles.zha.DeviceType.ON_OFF_PLUG_IN_UNIT: SWITCH,
        zigpy.profiles.zha.DeviceType.SMART_PLUG: SWITCH,
    },
    zigpy.profiles.zll.PROFILE_ID: {
        zigpy.profiles.zll.DeviceType.COLOR_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.DIMMABLE_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.DIMMABLE_PLUGIN_UNIT: LIGHT,
        zigpy.profiles.zll.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.ON_OFF_LIGHT: LIGHT,
        zigpy.profiles.zll.DeviceType.ON_OFF_PLUGIN_UNIT: SWITCH,
    },
}

DEVICE_TRACKER_CLUSTERS = SetRegistry()
EVENT_RELAY_CLUSTERS = SetRegistry()
LIGHT_CLUSTERS = SetRegistry()
OUTPUT_CHANNEL_ONLY_CLUSTERS = SetRegistry()

RADIO_TYPES = {
    RadioType.deconz.name: {
        ZHA_GW_RADIO: zigpy_deconz.api.Deconz,
        CONTROLLER: zigpy_deconz.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "Deconz",
    },
    RadioType.ezsp.name: {
        ZHA_GW_RADIO: bellows.ezsp.EZSP,
        CONTROLLER: bellows.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "EZSP",
    },
    RadioType.ti_cc.name: {
        ZHA_GW_RADIO: zigpy_cc.api.API,
        CONTROLLER: zigpy_cc.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "TI CC",
    },
    RadioType.xbee.name: {
        ZHA_GW_RADIO: zigpy_xbee.api.XBee,
        CONTROLLER: zigpy_xbee.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "XBee",
    },
    RadioType.zigate.name: {
        ZHA_GW_RADIO: zigpy_zigate.api.ZiGate,
        CONTROLLER: zigpy_zigate.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "ZiGate",
    },
}

COMPONENT_CLUSTERS = {
    BINARY_SENSOR: BINARY_SENSOR_CLUSTERS,
    DEVICE_TRACKER: DEVICE_TRACKER_CLUSTERS,
    LIGHT: LIGHT_CLUSTERS,
    SWITCH: SWITCH_CLUSTERS,
}

ZIGBEE_CHANNEL_REGISTRY = DictRegistry()


def set_or_callable(value):
    """Convert single str or None to a set. Pass through callables and sets."""
    if value is None:
        return frozenset()
    if callable(value):
        return value
    if isinstance(value, (frozenset, set, list)):
        return frozenset(value)
    return frozenset([str(value)])


@attr.s(frozen=True)
class MatchRule:
    """Match a ZHA Entity to a channel name or generic id."""

    channel_names: Union[Callable, Set[str], str] = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    generic_ids: Union[Callable, Set[str], str] = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    manufacturers: Union[Callable, Set[str], str] = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    models: Union[Callable, Set[str], str] = attr.ib(
        factory=frozenset, converter=set_or_callable
    )


class ZHAEntityRegistry:
    """Channel to ZHA Entity mapping."""

    def __init__(self):
        """Initialize Registry instance."""
        self._strict_registry = collections.defaultdict(dict)
        self._loose_registry = collections.defaultdict(dict)

    def get_entity(
        self, component: str, zha_device, chnls: dict, default: CALLABLE_T = None
    ) -> CALLABLE_T:
        """Match a ZHA Channels to a ZHA Entity class."""
        for match in self._strict_registry[component]:
            if self._strict_matched(zha_device, chnls, match):
                return self._strict_registry[component][match]

        return default

    def strict_match(
        self,
        component: str,
        channel_names: Union[Callable, Set[str], str] = None,
        generic_ids: Union[Callable, Set[str], str] = None,
        manufacturers: Union[Callable, Set[str], str] = None,
        models: Union[Callable, Set[str], str] = None,
    ) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Decorate a strict match rule."""

        rule = MatchRule(channel_names, generic_ids, manufacturers, models)

        def decorator(zha_ent: CALLABLE_T) -> CALLABLE_T:
            """Register a strict match rule.

            All non empty fields of a match rule must match.
            """
            self._strict_registry[component][rule] = zha_ent
            return zha_ent

        return decorator

    def loose_match(
        self,
        component: str,
        channel_names: Union[Callable, Set[str], str] = None,
        generic_ids: Union[Callable, Set[str], str] = None,
        manufacturers: Union[Callable, Set[str], str] = None,
        models: Union[Callable, Set[str], str] = None,
    ) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Decorate a loose match rule."""

        rule = MatchRule(channel_names, generic_ids, manufacturers, models)

        def decorator(zha_entity: CALLABLE_T) -> CALLABLE_T:
            """Register a loose match rule.

            All non empty fields of a match rule must match.
            """
            self._loose_registry[component][rule] = zha_entity
            return zha_entity

        return decorator

    def _strict_matched(self, zha_device, chnls: dict, rule: MatchRule) -> bool:
        """Return True if this device matches the criteria."""
        return all(self._matched(zha_device, chnls, rule))

    def _loose_matched(self, zha_device, chnls: dict, rule: MatchRule) -> bool:
        """Return True if this device matches the criteria."""
        return any(self._matched(zha_device, chnls, rule))

    @staticmethod
    def _matched(zha_device, chnls: dict, rule: MatchRule) -> list:
        """Return a list of field matches."""
        if not any(attr.asdict(rule).values()):
            return [False]

        matches = []
        if rule.channel_names:
            channel_names = {ch.name for ch in chnls}
            matches.append(rule.channel_names.issubset(channel_names))

        if rule.generic_ids:
            all_generic_ids = {ch.generic_id for ch in chnls}
            matches.append(rule.generic_ids.issubset(all_generic_ids))

        if rule.manufacturers:
            if callable(rule.manufacturers):
                matches.append(rule.manufacturers(zha_device.manufacturer))
            else:
                matches.append(zha_device.manufacturer in rule.manufacturers)

        if rule.models:
            if callable(rule.models):
                matches.append(rule.models(zha_device.model))
            else:
                matches.append(zha_device.model in rule.models)

        return matches


ZHA_ENTITIES = ZHAEntityRegistry()
