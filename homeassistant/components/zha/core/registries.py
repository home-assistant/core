"""Mapping registries for Zigbee Home Automation."""

from __future__ import annotations

import collections
from collections.abc import Callable
import dataclasses
from operator import attrgetter
from typing import TYPE_CHECKING, TypeVar

import attr
from zigpy import zcl
import zigpy.profiles.zha
import zigpy.profiles.zll
from zigpy.types.named import EUI64

from homeassistant.const import Platform

from .decorators import DictRegistry, NestedDictRegistry, SetRegistry

if TYPE_CHECKING:
    from ..entity import ZhaEntity, ZhaGroupEntity
    from .cluster_handlers import ClientClusterHandler, ClusterHandler


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
        zigpy.profiles.zha.DeviceType.IAS_ANCILLARY_CONTROL: Platform.ALARM_CONTROL_PANEL,
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

CLUSTER_HANDLER_ONLY_CLUSTERS = SetRegistry()
CLIENT_CLUSTER_HANDLER_REGISTRY: DictRegistry[type[ClientClusterHandler]] = (
    DictRegistry()
)
ZIGBEE_CLUSTER_HANDLER_REGISTRY: NestedDictRegistry[type[ClusterHandler]] = (
    NestedDictRegistry()
)

WEIGHT_ATTR = attrgetter("weight")


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
    """Match a ZHA Entity to a cluster handler name or generic id."""

    cluster_handler_names: frozenset[str] = attr.ib(
        factory=frozenset, converter=set_or_callable
    )
    generic_ids: frozenset[str] = attr.ib(factory=frozenset, converter=set_or_callable)
    manufacturers: frozenset[str] | Callable = attr.ib(
        factory=_get_empty_frozenset, converter=set_or_callable
    )
    models: frozenset[str] | Callable = attr.ib(
        factory=_get_empty_frozenset, converter=set_or_callable
    )
    aux_cluster_handlers: frozenset[str] | Callable = attr.ib(
        factory=_get_empty_frozenset, converter=set_or_callable
    )
    quirk_ids: frozenset[str] | Callable = attr.ib(
        factory=_get_empty_frozenset, converter=set_or_callable
    )

    @property
    def weight(self) -> int:
        """Return the weight of the matching rule.

        More specific matches should be preferred over less specific. Quirk class
        matching rules have priority over model matching rules
        and have a priority over manufacturer matching rules and rules matching a
        single model/manufacturer get a better priority over rules matching multiple
        models/manufacturers. And any model or manufacturers matching rules get better
        priority over rules matching only cluster handlers.
        But in case of a cluster handler name/cluster handler id matching, we give rules matching
        multiple cluster handlers a better priority over rules matching a single cluster handler.
        """
        weight = 0
        if self.quirk_ids:
            weight += 501 - (1 if callable(self.quirk_ids) else len(self.quirk_ids))

        if self.models:
            weight += 401 - (1 if callable(self.models) else len(self.models))

        if self.manufacturers:
            weight += 301 - (
                1 if callable(self.manufacturers) else len(self.manufacturers)
            )

        weight += 10 * len(self.cluster_handler_names)
        weight += 5 * len(self.generic_ids)
        if isinstance(self.aux_cluster_handlers, frozenset):
            weight += 1 * len(self.aux_cluster_handlers)
        return weight

    def claim_cluster_handlers(
        self, cluster_handlers: list[ClusterHandler]
    ) -> list[ClusterHandler]:
        """Return a list of cluster handlers this rule matches + aux cluster handlers."""
        claimed = []
        if isinstance(self.cluster_handler_names, frozenset):
            claimed.extend(
                [ch for ch in cluster_handlers if ch.name in self.cluster_handler_names]
            )
        if isinstance(self.generic_ids, frozenset):
            claimed.extend(
                [ch for ch in cluster_handlers if ch.generic_id in self.generic_ids]
            )
        if isinstance(self.aux_cluster_handlers, frozenset):
            claimed.extend(
                [ch for ch in cluster_handlers if ch.name in self.aux_cluster_handlers]
            )
        return claimed

    def strict_matched(
        self,
        manufacturer: str,
        model: str,
        cluster_handlers: list,
        quirk_id: str | None,
    ) -> bool:
        """Return True if this device matches the criteria."""
        return all(self._matched(manufacturer, model, cluster_handlers, quirk_id))

    def loose_matched(
        self,
        manufacturer: str,
        model: str,
        cluster_handlers: list,
        quirk_id: str | None,
    ) -> bool:
        """Return True if this device matches the criteria."""
        return any(self._matched(manufacturer, model, cluster_handlers, quirk_id))

    def _matched(
        self,
        manufacturer: str,
        model: str,
        cluster_handlers: list,
        quirk_id: str | None,
    ) -> list:
        """Return a list of field matches."""
        if not any(attr.asdict(self).values()):
            return [False]

        matches = []
        if self.cluster_handler_names:
            cluster_handler_names = {ch.name for ch in cluster_handlers}
            matches.append(self.cluster_handler_names.issubset(cluster_handler_names))

        if self.generic_ids:
            all_generic_ids = {ch.generic_id for ch in cluster_handlers}
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

        if self.quirk_ids:
            if callable(self.quirk_ids):
                matches.append(self.quirk_ids(quirk_id))
            else:
                matches.append(quirk_id in self.quirk_ids)

        return matches


@dataclasses.dataclass
class EntityClassAndClusterHandlers:
    """Container for entity class and corresponding cluster handlers."""

    entity_class: type[ZhaEntity]
    claimed_cluster_handlers: list[ClusterHandler]


class ZHAEntityRegistry:
    """Cluster handler to ZHA Entity mapping."""

    def __init__(self) -> None:
        """Initialize Registry instance."""
        self._strict_registry: dict[Platform, dict[MatchRule, type[ZhaEntity]]] = (
            collections.defaultdict(dict)
        )
        self._multi_entity_registry: dict[
            Platform, dict[int | str | None, dict[MatchRule, list[type[ZhaEntity]]]]
        ] = collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(list))
        )
        self._config_diagnostic_entity_registry: dict[
            Platform, dict[int | str | None, dict[MatchRule, list[type[ZhaEntity]]]]
        ] = collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(list))
        )
        self._group_registry: dict[str, type[ZhaGroupEntity]] = {}
        self.single_device_matches: dict[Platform, dict[EUI64, list[str]]] = (
            collections.defaultdict(lambda: collections.defaultdict(list))
        )

    def get_entity(
        self,
        component: Platform,
        manufacturer: str,
        model: str,
        cluster_handlers: list[ClusterHandler],
        quirk_id: str | None,
        default: type[ZhaEntity] | None = None,
    ) -> tuple[type[ZhaEntity] | None, list[ClusterHandler]]:
        """Match a ZHA ClusterHandler to a ZHA Entity class."""
        matches = self._strict_registry[component]
        for match in sorted(matches, key=WEIGHT_ATTR, reverse=True):
            if match.strict_matched(manufacturer, model, cluster_handlers, quirk_id):
                claimed = match.claim_cluster_handlers(cluster_handlers)
                return self._strict_registry[component][match], claimed

        return default, []

    def get_multi_entity(
        self,
        manufacturer: str,
        model: str,
        cluster_handlers: list[ClusterHandler],
        quirk_id: str | None,
    ) -> tuple[
        dict[Platform, list[EntityClassAndClusterHandlers]], list[ClusterHandler]
    ]:
        """Match ZHA cluster handlers to potentially multiple ZHA Entity classes."""
        result: dict[Platform, list[EntityClassAndClusterHandlers]] = (
            collections.defaultdict(list)
        )
        all_claimed: set[ClusterHandler] = set()
        for component, stop_match_groups in self._multi_entity_registry.items():
            for stop_match_grp, matches in stop_match_groups.items():
                sorted_matches = sorted(matches, key=WEIGHT_ATTR, reverse=True)
                for match in sorted_matches:
                    if match.strict_matched(
                        manufacturer, model, cluster_handlers, quirk_id
                    ):
                        claimed = match.claim_cluster_handlers(cluster_handlers)
                        for ent_class in stop_match_groups[stop_match_grp][match]:
                            ent_n_cluster_handlers = EntityClassAndClusterHandlers(
                                ent_class, claimed
                            )
                            result[component].append(ent_n_cluster_handlers)
                        all_claimed |= set(claimed)
                        if stop_match_grp:
                            break

        return result, list(all_claimed)

    def get_config_diagnostic_entity(
        self,
        manufacturer: str,
        model: str,
        cluster_handlers: list[ClusterHandler],
        quirk_id: str | None,
    ) -> tuple[
        dict[Platform, list[EntityClassAndClusterHandlers]], list[ClusterHandler]
    ]:
        """Match ZHA cluster handlers to potentially multiple ZHA Entity classes."""
        result: dict[Platform, list[EntityClassAndClusterHandlers]] = (
            collections.defaultdict(list)
        )
        all_claimed: set[ClusterHandler] = set()
        for (
            component,
            stop_match_groups,
        ) in self._config_diagnostic_entity_registry.items():
            for stop_match_grp, matches in stop_match_groups.items():
                sorted_matches = sorted(matches, key=WEIGHT_ATTR, reverse=True)
                for match in sorted_matches:
                    if match.strict_matched(
                        manufacturer, model, cluster_handlers, quirk_id
                    ):
                        claimed = match.claim_cluster_handlers(cluster_handlers)
                        for ent_class in stop_match_groups[stop_match_grp][match]:
                            ent_n_cluster_handlers = EntityClassAndClusterHandlers(
                                ent_class, claimed
                            )
                            result[component].append(ent_n_cluster_handlers)
                        all_claimed |= set(claimed)
                        if stop_match_grp:
                            break

        return result, list(all_claimed)

    def get_group_entity(self, component: str) -> type[ZhaGroupEntity] | None:
        """Match a ZHA group to a ZHA Entity class."""
        return self._group_registry.get(component)

    def strict_match(
        self,
        component: Platform,
        cluster_handler_names: set[str] | str | None = None,
        generic_ids: set[str] | str | None = None,
        manufacturers: Callable | set[str] | str | None = None,
        models: Callable | set[str] | str | None = None,
        aux_cluster_handlers: Callable | set[str] | str | None = None,
        quirk_ids: set[str] | str | None = None,
    ) -> Callable[[_ZhaEntityT], _ZhaEntityT]:
        """Decorate a strict match rule."""

        rule = MatchRule(
            cluster_handler_names,
            generic_ids,
            manufacturers,
            models,
            aux_cluster_handlers,
            quirk_ids,
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
        component: Platform,
        cluster_handler_names: set[str] | str | None = None,
        generic_ids: set[str] | str | None = None,
        manufacturers: Callable | set[str] | str | None = None,
        models: Callable | set[str] | str | None = None,
        aux_cluster_handlers: Callable | set[str] | str | None = None,
        stop_on_match_group: int | str | None = None,
        quirk_ids: set[str] | str | None = None,
    ) -> Callable[[_ZhaEntityT], _ZhaEntityT]:
        """Decorate a loose match rule."""

        rule = MatchRule(
            cluster_handler_names,
            generic_ids,
            manufacturers,
            models,
            aux_cluster_handlers,
            quirk_ids,
        )

        def decorator(zha_entity: _ZhaEntityT) -> _ZhaEntityT:
            """Register a loose match rule.

            All non empty fields of a match rule must match.
            """
            # group the rules by cluster handlers
            self._multi_entity_registry[component][stop_on_match_group][rule].append(
                zha_entity
            )
            return zha_entity

        return decorator

    def config_diagnostic_match(
        self,
        component: Platform,
        cluster_handler_names: set[str] | str | None = None,
        generic_ids: set[str] | str | None = None,
        manufacturers: Callable | set[str] | str | None = None,
        models: Callable | set[str] | str | None = None,
        aux_cluster_handlers: Callable | set[str] | str | None = None,
        stop_on_match_group: int | str | None = None,
        quirk_ids: set[str] | str | None = None,
    ) -> Callable[[_ZhaEntityT], _ZhaEntityT]:
        """Decorate a loose match rule."""

        rule = MatchRule(
            cluster_handler_names,
            generic_ids,
            manufacturers,
            models,
            aux_cluster_handlers,
            quirk_ids,
        )

        def decorator(zha_entity: _ZhaEntityT) -> _ZhaEntityT:
            """Register a loose match rule.

            All non-empty fields of a match rule must match.
            """
            # group the rules by cluster handlers
            self._config_diagnostic_entity_registry[component][stop_on_match_group][
                rule
            ].append(zha_entity)
            return zha_entity

        return decorator

    def group_match(
        self, component: Platform
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
