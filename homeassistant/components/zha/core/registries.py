"""Mapping registries for Zigbee Home Automation."""
from __future__ import annotations

import collections
from collections.abc import Callable
import dataclasses
from typing import TYPE_CHECKING, TypeVar

import attr
from zigpy import zcl
import zigpy.profiles.zha
import zigpy.profiles.zll
from zigpy.types.named import EUI64

from homeassistant.const import Platform

# importing channels updates registries
from . import channels as zha_channels  # noqa: F401 pylint: disable=unused-import
from .decorators import DictRegistry, SetRegistry

if TYPE_CHECKING:
    from ..entity import ZhaEntity, ZhaGroupEntity
    from .channels.base import ClientChannel, ZigbeeChannel


_ZhaEntityT = TypeVar("_ZhaEntityT", bound=type["ZhaEntity"])
_ZhaGroupEntityT = TypeVar("_ZhaGroupEntityT", bound=type["ZhaGroupEntity"])

GROUP_ENTITY_DOMAINS = [Platform.LIGHT, Platform.SWITCH, Platform.FAN]

IKEA_AIR_PURIFIER_CLUSTER = 0xFC7D
PHILLIPS_REMOTE_CLUSTER = 0xFC00
SMARTTHINGS_ACCELERATION_CLUSTER = 0xFC02
SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE = 0x8000
SMARTTHINGS_HUMIDITY_CLUSTER = 0xFC45
TUYA_MANUFACTURER_CLUSTER = 0xEF00
VOC_LEVEL_CLUSTER = 0x042E

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
REMOTE_DEVICE_TYPES = collections.defaultdict(list, REMOTE_DEVICE_TYPES)

SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {
    # this works for now but if we hit conflicts we can break it out to
    # a different dict that is keyed by manufacturer
    zcl.clusters.general.AnalogOutput.cluster_id: Platform.NUMBER,
    zcl.clusters.general.MultistateInput.cluster_id: Platform.SENSOR,
    zcl.clusters.general.OnOff.cluster_id: Platform.SWITCH,
    zcl.clusters.hvac.Fan.cluster_id: Platform.FAN,
}

SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {
    zcl.clusters.general.OnOff.cluster_id: Platform.BINARY_SENSOR,
    zcl.clusters.security.IasAce.cluster_id: Platform.ALARM_CONTROL_PANEL,
}

BINDABLE_CLUSTERS = SetRegistry()
CHANNEL_ONLY_CLUSTERS = SetRegistry()

DEVICE_CLASS = {
    zigpy.profiles.zha.PROFILE_ID: {
        SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE: Platform.DEVICE_TRACKER,
        zigpy.profiles.zha.DeviceType.THERMOSTAT: Platform.CLIMATE,
        zigpy.profiles.zha.DeviceType.COLOR_DIMMABLE_LIGHT: Platform.LIGHT,
        zigpy.profiles.zha.DeviceType.COLOR_TEMPERATURE_LIGHT: Platform.LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_BALLAST: Platform.LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_LIGHT: Platform.LIGHT,
        zigpy.profiles.zha.DeviceType.DIMMABLE_PLUG_IN_UNIT: Platform.LIGHT,
        zigpy.profiles.zha.DeviceType.EXTENDED_COLOR_LIGHT: Platform.LIGHT,
        zigpy.profiles.zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT: Platform.COVER,
        zigpy.profiles.zha.DeviceType.ON_OFF_BALLAST: Platform.SWITCH,
        zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT: Platform.LIGHT,
        zigpy.profiles.zha.DeviceType.ON_OFF_PLUG_IN_UNIT: Platform.SWITCH,
        zigpy.profiles.zha.DeviceType.SHADE: Platform.COVER,
        zigpy.profiles.zha.DeviceType.SMART_PLUG: Platform.SWITCH,
        zigpy.profiles.zha.DeviceType.IAS_ANCILLARY_CONTROL: (
            Platform.ALARM_CONTROL_PANEL
        ),
        zigpy.profiles.zha.DeviceType.IAS_WARNING_DEVICE: Platform.SIREN,
    },
    zigpy.profiles.zll.PROFILE_ID: {
        zigpy.profiles.zll.DeviceType.COLOR_LIGHT: Platform.LIGHT,
        zigpy.profiles.zll.DeviceType.COLOR_TEMPERATURE_LIGHT: Platform.LIGHT,
        zigpy.profiles.zll.DeviceType.DIMMABLE_LIGHT: Platform.LIGHT,
        zigpy.profiles.zll.DeviceType.DIMMABLE_PLUGIN_UNIT: Platform.LIGHT,
        zigpy.profiles.zll.DeviceType.EXTENDED_COLOR_LIGHT: Platform.LIGHT,
        zigpy.profiles.zll.DeviceType.ON_OFF_LIGHT: Platform.LIGHT,
        zigpy.profiles.zll.DeviceType.ON_OFF_PLUGIN_UNIT: Platform.SWITCH,
    },
}
DEVICE_CLASS = collections.defaultdict(dict, DEVICE_CLASS)

CLIENT_CHANNELS_REGISTRY: DictRegistry[type[ClientChannel]] = DictRegistry()
ZIGBEE_CHANNEL_REGISTRY: DictRegistry[type[ZigbeeChannel]] = DictRegistry()


def set_or_callable(value) -> frozenset[str] | Callable:
    """Convert single str or None to a set. Pass through callables and sets."""
    if value is None:
        return frozenset()
    if callable(value):
        return value
    if isinstance(value, (frozenset, set, list)):
        return frozenset(value)
    return frozenset([str(value)])


def _get_empty_frozenset() -> frozenset[str]:
    return frozenset()


@attr.s(frozen=True)
class MatchRule:
    """Match a ZHA Entity to a channel name or generic id."""

    channel_names: frozenset[str] = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    generic_ids: frozenset[str] = attr.ib(factory=frozenset, converter=set_or_callable)
    manufacturers: frozenset[str] | Callable = attr.ib(
        factory=_get_empty_frozenset, converter=set_or_callable
    )
    models: frozenset[str] | Callable = attr.ib(
        factory=_get_empty_frozenset, converter=set_or_callable
    )
    aux_channels: frozenset[str] | Callable = attr.ib(
        factory=_get_empty_frozenset, converter=set_or_callable
    )

    @property
    def weight(self) -> int:
        """Return the weight of the matching rule.

        More specific matches should be preferred over less specific. Model matching
        rules have a priority over manufacturer matching rules and rules matching a
        single model/manufacturer get a better priority over rules matching multiple
        models/manufacturers. And any model or manufacturers matching rules get better
        priority over rules matching only channels.
        But in case of a channel name/channel id matching, we give rules matching
        multiple channels a better priority over rules matching a single channel.
        """
        weight = 0
        if self.models:
            weight += 401 - (1 if callable(self.models) else len(self.models))

        if self.manufacturers:
            weight += 301 - (
                1 if callable(self.manufacturers) else len(self.manufacturers)
            )

        weight += 10 * len(self.channel_names)
        weight += 5 * len(self.generic_ids)
        if isinstance(self.aux_channels, frozenset):
            weight += 1 * len(self.aux_channels)
        return weight

    def claim_channels(self, channel_pool: list[ZigbeeChannel]) -> list[ZigbeeChannel]:
        """Return a list of channels this rule matches + aux channels."""
        claimed = []
        if isinstance(self.channel_names, frozenset):
            claimed.extend([ch for ch in channel_pool if ch.name in self.channel_names])
        if isinstance(self.generic_ids, frozenset):
            claimed.extend(
                [ch for ch in channel_pool if ch.generic_id in self.generic_ids]
            )
        if isinstance(self.aux_channels, frozenset):
            claimed.extend([ch for ch in channel_pool if ch.name in self.aux_channels])
        return claimed

    def strict_matched(self, manufacturer: str, model: str, channels: list) -> bool:
        """Return True if this device matches the criteria."""
        return all(self._matched(manufacturer, model, channels))

    def loose_matched(self, manufacturer: str, model: str, channels: list) -> bool:
        """Return True if this device matches the criteria."""
        return any(self._matched(manufacturer, model, channels))

    def _matched(self, manufacturer: str, model: str, channels: list) -> list:
        """Return a list of field matches."""
        if not any(attr.asdict(self).values()):
            return [False]

        matches = []
        if self.channel_names:
            channel_names = {ch.name for ch in channels}
            matches.append(self.channel_names.issubset(channel_names))

        if self.generic_ids:
            all_generic_ids = {ch.generic_id for ch in channels}
            matches.append(self.generic_ids.issubset(all_generic_ids))

        if self.manufacturers:
            if callable(self.manufacturers):
                matches.append(self.manufacturers(manufacturer))
            else:
                matches.append(manufacturer in self.manufacturers)

        if self.models:
            if callable(self.models):
                matches.append(self.models(model))
            else:
                matches.append(model in self.models)

        return matches


@dataclasses.dataclass
class EntityClassAndChannels:
    """Container for entity class and corresponding channels."""

    entity_class: type[ZhaEntity]
    claimed_channel: list[ZigbeeChannel]


class ZHAEntityRegistry:
    """Channel to ZHA Entity mapping."""

    def __init__(self) -> None:
        """Initialize Registry instance."""
        self._strict_registry: dict[
            str, dict[MatchRule, type[ZhaEntity]]
        ] = collections.defaultdict(dict)
        self._multi_entity_registry: dict[
            str, dict[int | str | None, dict[MatchRule, list[type[ZhaEntity]]]]
        ] = collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(list))
        )
        self._config_diagnostic_entity_registry: dict[
            str, dict[int | str | None, dict[MatchRule, list[type[ZhaEntity]]]]
        ] = collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(list))
        )
        self._group_registry: dict[str, type[ZhaGroupEntity]] = {}
        self.single_device_matches: dict[
            Platform, dict[EUI64, list[str]]
        ] = collections.defaultdict(lambda: collections.defaultdict(list))

    def get_entity(
        self,
        component: str,
        manufacturer: str,
        model: str,
        channels: list[ZigbeeChannel],
        default: type[ZhaEntity] | None = None,
    ) -> tuple[type[ZhaEntity] | None, list[ZigbeeChannel]]:
        """Match a ZHA Channels to a ZHA Entity class."""
        matches = self._strict_registry[component]
        for match in sorted(matches, key=lambda x: x.weight, reverse=True):
            if match.strict_matched(manufacturer, model, channels):
                claimed = match.claim_channels(channels)
                return self._strict_registry[component][match], claimed

        return default, []

    def get_multi_entity(
        self,
        manufacturer: str,
        model: str,
        channels: list[ZigbeeChannel],
    ) -> tuple[dict[str, list[EntityClassAndChannels]], list[ZigbeeChannel]]:
        """Match ZHA Channels to potentially multiple ZHA Entity classes."""
        result: dict[str, list[EntityClassAndChannels]] = collections.defaultdict(list)
        all_claimed: set[ZigbeeChannel] = set()
        for component, stop_match_groups in self._multi_entity_registry.items():
            for stop_match_grp, matches in stop_match_groups.items():
                sorted_matches = sorted(matches, key=lambda x: x.weight, reverse=True)
                for match in sorted_matches:
                    if match.strict_matched(manufacturer, model, channels):
                        claimed = match.claim_channels(channels)
                        for ent_class in stop_match_groups[stop_match_grp][match]:
                            ent_n_channels = EntityClassAndChannels(ent_class, claimed)
                            result[component].append(ent_n_channels)
                        all_claimed |= set(claimed)
                        if stop_match_grp:
                            break

        return result, list(all_claimed)

    def get_config_diagnostic_entity(
        self,
        manufacturer: str,
        model: str,
        channels: list[ZigbeeChannel],
    ) -> tuple[dict[str, list[EntityClassAndChannels]], list[ZigbeeChannel]]:
        """Match ZHA Channels to potentially multiple ZHA Entity classes."""
        result: dict[str, list[EntityClassAndChannels]] = collections.defaultdict(list)
        all_claimed: set[ZigbeeChannel] = set()
        for (
            component,
            stop_match_groups,
        ) in self._config_diagnostic_entity_registry.items():
            for stop_match_grp, matches in stop_match_groups.items():
                sorted_matches = sorted(matches, key=lambda x: x.weight, reverse=True)
                for match in sorted_matches:
                    if match.strict_matched(manufacturer, model, channels):
                        claimed = match.claim_channels(channels)
                        for ent_class in stop_match_groups[stop_match_grp][match]:
                            ent_n_channels = EntityClassAndChannels(ent_class, claimed)
                            result[component].append(ent_n_channels)
                        all_claimed |= set(claimed)
                        if stop_match_grp:
                            break

        return result, list(all_claimed)

    def get_group_entity(self, component: str) -> type[ZhaGroupEntity] | None:
        """Match a ZHA group to a ZHA Entity class."""
        return self._group_registry.get(component)

    def strict_match(
        self,
        component: str,
        channel_names: set[str] | str | None = None,
        generic_ids: set[str] | str | None = None,
        manufacturers: Callable | set[str] | str | None = None,
        models: Callable | set[str] | str | None = None,
        aux_channels: Callable | set[str] | str | None = None,
    ) -> Callable[[_ZhaEntityT], _ZhaEntityT]:
        """Decorate a strict match rule."""

        rule = MatchRule(
            channel_names, generic_ids, manufacturers, models, aux_channels
        )

        def decorator(zha_ent: _ZhaEntityT) -> _ZhaEntityT:
            """Register a strict match rule.

            All non-empty fields of a match rule must match.
            """
            self._strict_registry[component][rule] = zha_ent
            return zha_ent

        return decorator

    def multipass_match(
        self,
        component: str,
        channel_names: set[str] | str | None = None,
        generic_ids: set[str] | str | None = None,
        manufacturers: Callable | set[str] | str | None = None,
        models: Callable | set[str] | str | None = None,
        aux_channels: Callable | set[str] | str | None = None,
        stop_on_match_group: int | str | None = None,
    ) -> Callable[[_ZhaEntityT], _ZhaEntityT]:
        """Decorate a loose match rule."""

        rule = MatchRule(
            channel_names,
            generic_ids,
            manufacturers,
            models,
            aux_channels,
        )

        def decorator(zha_entity: _ZhaEntityT) -> _ZhaEntityT:
            """Register a loose match rule.

            All non empty fields of a match rule must match.
            """
            # group the rules by channels
            self._multi_entity_registry[component][stop_on_match_group][rule].append(
                zha_entity
            )
            return zha_entity

        return decorator

    def config_diagnostic_match(
        self,
        component: str,
        channel_names: set[str] | str | None = None,
        generic_ids: set[str] | str | None = None,
        manufacturers: Callable | set[str] | str | None = None,
        models: Callable | set[str] | str | None = None,
        aux_channels: Callable | set[str] | str | None = None,
        stop_on_match_group: int | str | None = None,
    ) -> Callable[[_ZhaEntityT], _ZhaEntityT]:
        """Decorate a loose match rule."""

        rule = MatchRule(
            channel_names,
            generic_ids,
            manufacturers,
            models,
            aux_channels,
        )

        def decorator(zha_entity: _ZhaEntityT) -> _ZhaEntityT:
            """Register a loose match rule.

            All non-empty fields of a match rule must match.
            """
            # group the rules by channels
            self._config_diagnostic_entity_registry[component][stop_on_match_group][
                rule
            ].append(zha_entity)
            return zha_entity

        return decorator

    def group_match(
        self, component: str
    ) -> Callable[[_ZhaGroupEntityT], _ZhaGroupEntityT]:
        """Decorate a group match rule."""

        def decorator(zha_ent: _ZhaGroupEntityT) -> _ZhaGroupEntityT:
            """Register a group match rule."""
            self._group_registry[component] = zha_ent
            return zha_ent

        return decorator

    def prevent_entity_creation(self, platform: Platform, ieee: EUI64, key: str):
        """Return True if the entity should not be created."""
        platform_restrictions = self.single_device_matches[platform]
        device_restrictions = platform_restrictions[ieee]
        if key in device_restrictions:
            return True
        device_restrictions.append(key)
        return False

    def clean_up(self) -> None:
        """Clean up post discovery."""
        self.single_device_matches = collections.defaultdict(
            lambda: collections.defaultdict(list)
        )


ZHA_ENTITIES = ZHAEntityRegistry()
