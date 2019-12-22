"""
Mapping registries for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import collections
from typing import Callable, Set

import attr
import bellows.ezsp
import bellows.zigbee.application
import zigpy.profiles.zha
import zigpy.profiles.zll
import zigpy.zcl as zcl
import zigpy_deconz.api
import zigpy_deconz.zigbee.application
import zigpy_xbee.api
import zigpy_xbee.zigbee.application
import zigpy_zigate.api
import zigpy_zigate.zigbee.application

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
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

BINARY_SENSOR_CLUSTERS = SetRegistry()
BINDABLE_CLUSTERS = SetRegistry()
CHANNEL_ONLY_CLUSTERS = SetRegistry()
CLUSTER_REPORT_CONFIGS = {}
CUSTOM_CLUSTER_MAPPINGS = {}
DEVICE_CLASS = collections.defaultdict(dict)
DEVICE_TRACKER_CLUSTERS = SetRegistry()
EVENT_RELAY_CLUSTERS = SetRegistry()
LIGHT_CLUSTERS = SetRegistry()
OUTPUT_CHANNEL_ONLY_CLUSTERS = SetRegistry()
RADIO_TYPES = {}
REMOTE_DEVICE_TYPES = collections.defaultdict(list)
SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {}
SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {}
SWITCH_CLUSTERS = SetRegistry()
SMARTTHINGS_ACCELERATION_CLUSTER = 0xFC02
SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE = 0x8000
SMARTTHINGS_HUMIDITY_CLUSTER = 0xFC45

COMPONENT_CLUSTERS = {
    BINARY_SENSOR: BINARY_SENSOR_CLUSTERS,
    DEVICE_TRACKER: DEVICE_TRACKER_CLUSTERS,
    LIGHT: LIGHT_CLUSTERS,
    SWITCH: SWITCH_CLUSTERS,
}

ZIGBEE_CHANNEL_REGISTRY = DictRegistry()


def establish_device_mappings():
    """Establish mappings between ZCL objects and HA ZHA objects.

    These cannot be module level, as importing bellows must be done in a
    in a function.
    """
    RADIO_TYPES[RadioType.ezsp.name] = {
        ZHA_GW_RADIO: bellows.ezsp.EZSP,
        CONTROLLER: bellows.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "EZSP",
    }

    RADIO_TYPES[RadioType.deconz.name] = {
        ZHA_GW_RADIO: zigpy_deconz.api.Deconz,
        CONTROLLER: zigpy_deconz.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "Deconz",
    }

    RADIO_TYPES[RadioType.xbee.name] = {
        ZHA_GW_RADIO: zigpy_xbee.api.XBee,
        CONTROLLER: zigpy_xbee.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "XBee",
    }

    RADIO_TYPES[RadioType.zigate.name] = {
        ZHA_GW_RADIO: zigpy_zigate.api.ZiGate,
        CONTROLLER: zigpy_zigate.zigbee.application.ControllerApplication,
        ZHA_GW_RADIO_DESCRIPTION: "ZiGate",
    }

    BINARY_SENSOR_CLUSTERS.add(SMARTTHINGS_ACCELERATION_CLUSTER)

    DEVICE_CLASS[zigpy.profiles.zha.PROFILE_ID].update(
        {
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
            zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT_SWITCH: SWITCH,
            zigpy.profiles.zha.DeviceType.ON_OFF_PLUG_IN_UNIT: SWITCH,
            zigpy.profiles.zha.DeviceType.SMART_PLUG: SWITCH,
        }
    )

    DEVICE_CLASS[zigpy.profiles.zll.PROFILE_ID].update(
        {
            zigpy.profiles.zll.DeviceType.COLOR_LIGHT: LIGHT,
            zigpy.profiles.zll.DeviceType.COLOR_TEMPERATURE_LIGHT: LIGHT,
            zigpy.profiles.zll.DeviceType.DIMMABLE_LIGHT: LIGHT,
            zigpy.profiles.zll.DeviceType.DIMMABLE_PLUGIN_UNIT: LIGHT,
            zigpy.profiles.zll.DeviceType.EXTENDED_COLOR_LIGHT: LIGHT,
            zigpy.profiles.zll.DeviceType.ON_OFF_LIGHT: LIGHT,
            zigpy.profiles.zll.DeviceType.ON_OFF_PLUGIN_UNIT: SWITCH,
        }
    )

    SINGLE_INPUT_CLUSTER_DEVICE_CLASS.update(
        {
            # this works for now but if we hit conflicts we can break it out to
            # a different dict that is keyed by manufacturer
            SMARTTHINGS_ACCELERATION_CLUSTER: BINARY_SENSOR,
            SMARTTHINGS_HUMIDITY_CLUSTER: SENSOR,
            zcl.clusters.closures.DoorLock: LOCK,
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
    )

    SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS.update(
        {zcl.clusters.general.OnOff: BINARY_SENSOR}
    )

    zha = zigpy.profiles.zha
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(zha.DeviceType.COLOR_CONTROLLER)
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(zha.DeviceType.COLOR_DIMMER_SWITCH)
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(zha.DeviceType.COLOR_SCENE_CONTROLLER)
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(zha.DeviceType.DIMMER_SWITCH)
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(zha.DeviceType.NON_COLOR_CONTROLLER)
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(
        zha.DeviceType.NON_COLOR_SCENE_CONTROLLER
    )
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(zha.DeviceType.REMOTE_CONTROL)
    REMOTE_DEVICE_TYPES[zha.PROFILE_ID].append(zha.DeviceType.SCENE_SELECTOR)

    zll = zigpy.profiles.zll
    REMOTE_DEVICE_TYPES[zll.PROFILE_ID].append(zll.DeviceType.COLOR_CONTROLLER)
    REMOTE_DEVICE_TYPES[zll.PROFILE_ID].append(zll.DeviceType.COLOR_SCENE_CONTROLLER)
    REMOTE_DEVICE_TYPES[zll.PROFILE_ID].append(zll.DeviceType.CONTROL_BRIDGE)
    REMOTE_DEVICE_TYPES[zll.PROFILE_ID].append(zll.DeviceType.CONTROLLER)
    REMOTE_DEVICE_TYPES[zll.PROFILE_ID].append(zll.DeviceType.SCENE_CONTROLLER)


@attr.s(frozen=True)
class MatchRule:
    """Match a ZHA Entity to a channel name or generic id."""

    channel_names: Set[str] = attr.ib(factory=frozenset, converter=frozenset)
    generic_ids: Set[str] = attr.ib(factory=frozenset, converter=frozenset)
    manufacturer: str = attr.ib(default=None)
    model: str = attr.ib(default=None)


class ZHAEntityRegistry:
    """Channel to ZHA Entity mapping."""

    def __init__(self):
        """Initialize Registry instance."""
        self._strict_registry = collections.defaultdict(dict)
        self._loose_registry = collections.defaultdict(dict)

    def get_entity(
        self, component: str, zha_device, chnls: list, default: CALLABLE_T = None
    ) -> CALLABLE_T:
        """Match a ZHA Channels to a ZHA Entity class."""
        for match in self._strict_registry[component]:
            if self._strict_matched(zha_device, chnls, match):
                return self._strict_registry[component][match]

        return default

    def strict_match(
        self, component: str, rule: MatchRule
    ) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Decorate a strict match rule."""

        def decorator(zha_ent: CALLABLE_T) -> CALLABLE_T:
            """Register a strict match rule.

            All non empty fields of a match rule must match.
            """
            self._strict_registry[component][rule] = zha_ent
            return zha_ent

        return decorator

    def loose_match(
        self, component: str, rule: MatchRule
    ) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Decorate a loose match rule."""

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
    def _matched(zha_device, chnls: list, rule: MatchRule) -> bool:
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

        if rule.manufacturer:
            matches.append(zha_device.manufacturer == rule.manufacturer)

        if rule.model:
            matches.append(zha_device.model == rule.model)

        return matches


ZHA_ENTITIES = ZHAEntityRegistry()
