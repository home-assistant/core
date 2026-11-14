"""Entity suggestions from entity configurations that already exist.

Suggests the configuration of an entity created through the UI for the other
channels of its device and of identically programmed devices. Everything the
configuration says besides its group addresses - inverted values, sync state,
travel times, temperature limits … - is kept, so a channel wired like one that
is already set up doesn't have to be filled in again.

The group address side is derived by `ga_mapping`, which knows nothing about
the configuration format; this module only reads the addresses out of stored
UI configurations and writes the derived ones back into a copy of them.
"""

from collections import Counter
from copy import deepcopy
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TypedDict, override

import probatio
from xknx.exceptions import CouldNotParseAddress
from xknx.telegram.address import GroupAddress, parse_device_group_address
from xknxproject.models import KNXProject

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ...const import DOMAIN
from ..const import CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE
from ..entity_store_schema import KNX_SCHEMA_FOR_PLATFORM
from .base import SuggestionProvider
from .const import (
    PlatformSuggestion,
    ProviderResult,
    ProviderSuggestion,
    SuggestedGroupAddress,
)
from .ga_mapping import (
    ChannelMapping,
    GaSlot,
    SourceAddress,
    build_project_index,
    derive_channel_mappings,
)

if TYPE_CHECKING:
    from ...knx_module import KNXModule
    from ..config_store import KNXEntityStoreModel

type ConfigPath = tuple[str, ...]

# the keys of a group address config that address a single group address
_SLOTS: tuple[GaSlot, ...] = (CONF_GA_WRITE, CONF_GA_STATE)


class ExistingConfigState(StrEnum):
    """Availability of the data existing configurations are matched against."""

    NO_PROJECT = "no_project"
    NO_UI_ENTITIES = "no_ui_entities"
    OK = "ok"


class ExistingConfigHints(TypedDict):
    """Hints of the existing configuration provider."""

    state: ExistingConfigState


def _project_address(address: str | int | None) -> str | None:
    """Render a configured group address the way project data names it.

    Configurations keep addresses as they were entered - in any address style
    or as raw number.
    """
    if address is None:
        return None
    try:
        parsed = parse_device_group_address(address)
    except CouldNotParseAddress:
        return None
    # internal group addresses are not part of a project
    return str(parsed) if isinstance(parsed, GroupAddress) else None


def _iter_ga_configs(
    config: dict[str, Any], path: ConfigPath = ()
) -> list[tuple[ConfigPath, dict[str, Any]]]:
    """Return the group address configs of a `knx` config with their path."""
    ga_configs: list[tuple[ConfigPath, dict[str, Any]]] = []
    for key, value in config.items():
        if not isinstance(value, dict):
            continue
        if any(slot in value for slot in (*_SLOTS, CONF_GA_PASSIVE)):
            ga_configs.append(((*path, key), value))
        else:
            # a section or the chosen option of a group select
            ga_configs.extend(_iter_ga_configs(value, (*path, key)))
    return ga_configs


def _reference(path: ConfigPath, slot: GaSlot) -> str:
    """Name a `write` or `state` key of a config - eg. "ga_switch.write"."""
    return ".".join((*path, slot))


def _source_addresses(config: dict[str, Any]) -> list[SourceAddress]:
    """Read the addressed group addresses out of a `knx` config.

    Passive addresses are left out - they are alternative addresses of the same
    function, so they say nothing about which channel a configuration is on.
    """
    return [
        SourceAddress(_reference(path, slot), address, slot)
        for path, ga_config in _iter_ga_configs(config)
        for slot in _SLOTS
        if (address := _project_address(ga_config.get(slot))) is not None
    ]


def _apply(config: dict[str, Any], mapping: ChannelMapping) -> dict[str, Any]:
    """Copy a `knx` config with the addresses of the target channel.

    A group address config the mapping doesn't mention is device global
    (eg. a central heating/cooling switchover) and keeps the addresses it has.
    """
    result = deepcopy(config)
    for path, ga_config in _iter_ga_configs(result):
        passive: list[str] = []
        replaced = False
        for slot in _SLOTS:
            reference = _reference(path, slot)
            if (mapped := mapping.addresses.get(reference)) is not None:
                ga_config[slot] = mapped.address
                passive.extend(
                    address for address in mapped.passive if address not in passive
                )
                replaced = True
            elif reference in mapping.unmatched:
                ga_config[slot] = None
                replaced = True
        if replaced and CONF_GA_PASSIVE in ga_config:
            # the passive addresses of the source belong to its channel
            ga_config[CONF_GA_PASSIVE] = passive
        if not any(ga_config.get(key) for key in (*_SLOTS, CONF_GA_PASSIVE)):
            # the target channel doesn't offer this function - optional keys
            # are left unset, a config missing a required one is not suggested
            parent = result
            for key in path[:-1]:
                parent = parent[key]
            del parent[path[-1]]
    return result


def _validates(platform: Platform, knx_config: dict[str, Any]) -> bool:
    """Check whether a suggested `knx` config passes the platform schema."""
    try:
        KNX_SCHEMA_FOR_PLATFORM[platform](knx_config)
    except probatio.Invalid:
        return False
    return True


def _project_addresses(knx_config: dict[str, Any]) -> list[str]:
    """Return the group addresses a `knx` config uses, as project data names them."""
    return list(
        dict.fromkeys(
            project_address
            for _, ga_config in _iter_ga_configs(knx_config)
            for address in (
                *(ga_config.get(slot) for slot in _SLOTS),
                *(ga_config.get(CONF_GA_PASSIVE) or ()),
            )
            if (project_address := _project_address(address)) is not None
        )
    )


def _matched_group_addresses(
    project: KNXProject, knx_config: dict[str, Any], template: dict[str, Any]
) -> list[SuggestedGroupAddress]:
    """Return the group addresses a suggested `knx` config uses on its own.

    Addresses shared with the template - eg. a central switchover - are left
    out: they are used by the template entity, which doesn't make the suggested
    channel an already configured one.
    """
    shared = set(_project_addresses(template))
    return [
        SuggestedGroupAddress(
            address=address, name=project["group_addresses"][address]["name"]
        )
        for address in _project_addresses(knx_config)
        if address not in shared and address in project["group_addresses"]
    ]


def _suggested_name(
    project: KNXProject, mapping: ChannelMapping, knx_config: dict[str, Any]
) -> str:
    """Name a suggestion after its channel, or after what it acts on.

    Applications without channels name their objects "Output A", "Channel B" …
    - the group addresses are what says which room is meant there.
    """
    if (
        mapping.target.channel
        not in (project["devices"][mapping.target.device]["channels"])
    ):
        for _, ga_config in _iter_ga_configs(knx_config):
            if (address := ga_config.get(CONF_GA_WRITE)) and (
                group_address := project["group_addresses"].get(address)
            ):
                return group_address["name"]
    return mapping.channel_name or mapping.device_name


def _disambiguate_names(suggestions: list[ProviderSuggestion]) -> None:
    """Prefix names used multiple times with their device name."""
    name_counts = Counter(suggestion["suggested_name"] for suggestion in suggestions)
    for suggestion in suggestions:
        if name_counts[suggestion["suggested_name"]] > 1:
            suggestion["suggested_name"] = (
                f"{suggestion['group_name']} {suggestion['suggested_name']}"
            )


def _build_suggestions(
    project: KNXProject,
    entities: KNXEntityStoreModel,
    entity_registry: er.EntityRegistry,
) -> list[ProviderSuggestion]:
    """Build suggestions for the channels wired like a configured entity."""
    index = build_project_index(project)
    # the best suggestion of each channel and platform with its coverage - eg.
    # a dimmable light describes a dimmer channel better than a switched one
    best: dict[tuple[str, str, str], tuple[tuple[int, int], ProviderSuggestion]] = {}
    for platform, configs in entities.items():
        if platform not in KNX_SCHEMA_FOR_PLATFORM:
            continue
        for unique_id, config in configs.items():
            template: dict[str, Any] = config[DOMAIN]
            if not (addresses := _source_addresses(template)):
                continue
            entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
            for mapping in derive_channel_mappings(index, addresses):
                key = (mapping.target.device, mapping.target.channel, platform)
                coverage = (len(mapping.addresses), -len(mapping.unmatched))
                if key in best and best[key][0] >= coverage:
                    continue
                knx_config = _apply(template, mapping)
                # the schema decides what a complete configuration needs
                if not _validates(Platform(platform), knx_config):
                    continue
                best[key] = (
                    coverage,
                    ProviderSuggestion(
                        # channels are only unique within a device, and a
                        # channel may be suggested for multiple platforms
                        id="_".join(key),
                        suggested_name=_suggested_name(project, mapping, knx_config),
                        group_id=mapping.target.device,
                        group_name=mapping.device_name,
                        secondary_info=mapping.channel_name,
                        platform_options=[platform],
                        suggestions={
                            platform: PlatformSuggestion(
                                knx=knx_config,
                                matched_group_addresses=_matched_group_addresses(
                                    project, knx_config, template
                                ),
                                unmatched=sorted(mapping.unmatched),
                            )
                        },
                        metadata={"template_entity_id": entity_id},
                    ),
                )
    suggestions = [suggestion for _, suggestion in best.values()]
    _disambiguate_names(suggestions)
    return suggestions


class ExistingConfigSuggestionProvider(SuggestionProvider):
    """Suggest entities for channels wired like an already configured one."""

    provider_id = "cfg"

    @override
    async def async_get_suggestions(
        self, hass: HomeAssistant, knx: KNXModule
    ) -> ProviderResult:
        """Generate entity suggestions from the stored UI configurations."""
        project = await knx.project.get_knxproject()
        if project is None:
            return ProviderResult(
                suggestions=[],
                hints=ExistingConfigHints(state=ExistingConfigState.NO_PROJECT),
            )
        entities = knx.config_store.data["entities"]
        if not any(entities.values()):
            return ProviderResult(
                suggestions=[],
                hints=ExistingConfigHints(state=ExistingConfigState.NO_UI_ENTITIES),
            )
        return ProviderResult(
            suggestions=_build_suggestions(project, entities, er.async_get(hass)),
            hints=ExistingConfigHints(state=ExistingConfigState.OK),
        )
