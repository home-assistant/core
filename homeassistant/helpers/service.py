"""Service calling related helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
import dataclasses
from enum import Enum
from functools import cache, partial
import logging
from types import ModuleType
from typing import TYPE_CHECKING, Any, TypedDict, TypeGuard, cast

import voluptuous as vol

from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_CONTROL
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ACTION,
    CONF_ENTITY_ID,
    CONF_SERVICE_DATA,
    CONF_SERVICE_DATA_TEMPLATE,
    CONF_SERVICE_TEMPLATE,
    CONF_TARGET,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
)
from homeassistant.core import (
    Context,
    EntityServiceResponse,
    HassJob,
    HassJobType,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotSupported,
    TemplateError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.loader import Integration, async_get_integrations, bind_hass
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.yaml import load_yaml_dict
from homeassistant.util.yaml.loader import JSON_TYPE

from . import (
    area_registry,
    config_validation as cv,
    device_registry,
    entity_registry,
    floor_registry,
    label_registry,
    template,
    translation,
)
from .group import expand_entity_ids
from .selector import TargetSelector
from .typing import ConfigType, TemplateVarsType, VolDictType, VolSchemaType

if TYPE_CHECKING:
    from .entity import Entity

CONF_SERVICE_ENTITY_ID = "entity_id"

_LOGGER = logging.getLogger(__name__)

SERVICE_DESCRIPTION_CACHE: HassKey[dict[tuple[str, str], dict[str, Any] | None]] = (
    HassKey("service_description_cache")
)
ALL_SERVICE_DESCRIPTIONS_CACHE: HassKey[
    tuple[set[tuple[str, str]], dict[str, dict[str, Any]]]
] = HassKey("all_service_descriptions_cache")


@cache
def _base_components() -> dict[str, ModuleType]:
    """Return a cached lookup of base components."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import (
        alarm_control_panel,
        calendar,
        camera,
        climate,
        cover,
        fan,
        humidifier,
        light,
        lock,
        media_player,
        notify,
        remote,
        siren,
        todo,
        update,
        vacuum,
        water_heater,
    )

    return {
        "alarm_control_panel": alarm_control_panel,
        "calendar": calendar,
        "camera": camera,
        "climate": climate,
        "cover": cover,
        "fan": fan,
        "humidifier": humidifier,
        "light": light,
        "lock": lock,
        "media_player": media_player,
        "notify": notify,
        "remote": remote,
        "siren": siren,
        "todo": todo,
        "update": update,
        "vacuum": vacuum,
        "water_heater": water_heater,
    }


def _validate_option_or_feature(option_or_feature: str, label: str) -> Any:
    """Validate attribute option or supported feature."""
    try:
        domain, enum, option = option_or_feature.split(".", 2)
    except ValueError as exc:
        raise vol.Invalid(
            f"Invalid {label} '{option_or_feature}', expected <domain>.<enum>.<member>"
        ) from exc

    base_components = _base_components()
    if not (base_component := base_components.get(domain)):
        raise vol.Invalid(f"Unknown base component '{domain}'")

    try:
        attribute_enum = getattr(base_component, enum)
    except AttributeError as exc:
        raise vol.Invalid(f"Unknown {label} enum '{domain}.{enum}'") from exc

    if not issubclass(attribute_enum, Enum):
        raise vol.Invalid(f"Expected {label} '{domain}.{enum}' to be an enum")

    try:
        return getattr(attribute_enum, option).value
    except AttributeError as exc:
        raise vol.Invalid(f"Unknown {label} '{enum}.{option}'") from exc


def validate_attribute_option(attribute_option: str) -> Any:
    """Validate attribute option."""
    return _validate_option_or_feature(attribute_option, "attribute option")


def validate_supported_feature(supported_feature: str) -> Any:
    """Validate supported feature."""
    return _validate_option_or_feature(supported_feature, "supported feature")


# Basic schemas which translate attribute and supported feature enum names
# to their values. Full validation is done by hassfest.services
_FIELD_SCHEMA = vol.Schema(
    {
        vol.Optional("filter"): {
            vol.Optional("attribute"): {
                vol.Required(str): [vol.All(str, validate_attribute_option)],
            },
            vol.Optional("supported_features"): [
                vol.All(str, validate_supported_feature)
            ],
        },
    },
    extra=vol.ALLOW_EXTRA,
)

_SECTION_SCHEMA = vol.Schema(
    {
        vol.Required("fields"): vol.Schema({str: _FIELD_SCHEMA}),
    },
    extra=vol.ALLOW_EXTRA,
)

_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("target"): vol.Any(TargetSelector.CONFIG_SCHEMA, None),
        vol.Optional("fields"): vol.Schema(
            {str: vol.Any(_SECTION_SCHEMA, _FIELD_SCHEMA)}
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise vol.Invalid("Key does not start with .")
    return key


_SERVICES_SCHEMA = vol.Schema(
    {
        vol.Remove(vol.All(str, starts_with_dot)): object,
        cv.slug: vol.Any(None, _SERVICE_SCHEMA),
    }
)


class ServiceParams(TypedDict):
    """Type for service call parameters."""

    domain: str
    service: str
    service_data: dict[str, Any]
    target: dict | None


class ServiceTargetSelector:
    """Class to hold a target selector for a service."""

    __slots__ = ("entity_ids", "device_ids", "area_ids", "floor_ids", "label_ids")

    def __init__(self, service_call: ServiceCall) -> None:
        """Extract ids from service call data."""
        service_call_data = service_call.data
        entity_ids: str | list | None = service_call_data.get(ATTR_ENTITY_ID)
        device_ids: str | list | None = service_call_data.get(ATTR_DEVICE_ID)
        area_ids: str | list | None = service_call_data.get(ATTR_AREA_ID)
        floor_ids: str | list | None = service_call_data.get(ATTR_FLOOR_ID)
        label_ids: str | list | None = service_call_data.get(ATTR_LABEL_ID)

        self.entity_ids = (
            set(cv.ensure_list(entity_ids)) if _has_match(entity_ids) else set()
        )
        self.device_ids = (
            set(cv.ensure_list(device_ids)) if _has_match(device_ids) else set()
        )
        self.area_ids = set(cv.ensure_list(area_ids)) if _has_match(area_ids) else set()
        self.floor_ids = (
            set(cv.ensure_list(floor_ids)) if _has_match(floor_ids) else set()
        )
        self.label_ids = (
            set(cv.ensure_list(label_ids)) if _has_match(label_ids) else set()
        )

    @property
    def has_any_selector(self) -> bool:
        """Determine if any selectors are present."""
        return bool(
            self.entity_ids
            or self.device_ids
            or self.area_ids
            or self.floor_ids
            or self.label_ids
        )


@dataclasses.dataclass(slots=True)
class SelectedEntities:
    """Class to hold the selected entities."""

    # Entities that were explicitly mentioned.
    referenced: set[str] = dataclasses.field(default_factory=set)

    # Entities that were referenced via device/area/floor/label ID.
    # Should not trigger a warning when they don't exist.
    indirectly_referenced: set[str] = dataclasses.field(default_factory=set)

    # Referenced items that could not be found.
    missing_devices: set[str] = dataclasses.field(default_factory=set)
    missing_areas: set[str] = dataclasses.field(default_factory=set)
    missing_floors: set[str] = dataclasses.field(default_factory=set)
    missing_labels: set[str] = dataclasses.field(default_factory=set)

    # Referenced devices
    referenced_devices: set[str] = dataclasses.field(default_factory=set)
    referenced_areas: set[str] = dataclasses.field(default_factory=set)

    def log_missing(self, missing_entities: set[str]) -> None:
        """Log about missing items."""
        parts = []
        for label, items in (
            ("floors", self.missing_floors),
            ("areas", self.missing_areas),
            ("devices", self.missing_devices),
            ("entities", missing_entities),
            ("labels", self.missing_labels),
        ):
            if items:
                parts.append(f"{label} {', '.join(sorted(items))}")

        if not parts:
            return

        _LOGGER.warning(
            "Referenced %s are missing or not currently available",
            ", ".join(parts),
        )


@bind_hass
def call_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    blocking: bool = False,
    variables: TemplateVarsType = None,
    validate_config: bool = True,
) -> None:
    """Call a service based on a config hash."""
    asyncio.run_coroutine_threadsafe(
        async_call_from_config(hass, config, blocking, variables, validate_config),
        hass.loop,
    ).result()


@bind_hass
async def async_call_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    blocking: bool = False,
    variables: TemplateVarsType = None,
    validate_config: bool = True,
    context: Context | None = None,
) -> None:
    """Call a service based on a config hash."""
    try:
        params = async_prepare_call_from_config(
            hass, config, variables, validate_config
        )
    except HomeAssistantError as ex:
        if blocking:
            raise
        _LOGGER.error(ex)
    else:
        await hass.services.async_call(**params, blocking=blocking, context=context)


@callback
@bind_hass
def async_prepare_call_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType = None,
    validate_config: bool = False,
) -> ServiceParams:
    """Prepare to call a service based on a config hash."""
    if validate_config:
        try:
            config = cv.SERVICE_SCHEMA(config)
        except vol.Invalid as ex:
            raise HomeAssistantError(
                f"Invalid config for calling service: {ex}"
            ) from ex

    if CONF_ACTION in config:
        domain_service = config[CONF_ACTION]
    else:
        domain_service = config[CONF_SERVICE_TEMPLATE]

    if isinstance(domain_service, template.Template):
        try:
            domain_service = domain_service.async_render(variables)
            domain_service = cv.service(domain_service)
        except TemplateError as ex:
            raise HomeAssistantError(
                f"Error rendering service name template: {ex}"
            ) from ex
        except vol.Invalid as ex:
            raise HomeAssistantError(
                f"Template rendered invalid service: {domain_service}"
            ) from ex

    domain, _, service = domain_service.partition(".")

    target = {}
    if CONF_TARGET in config:
        conf = config[CONF_TARGET]
        try:
            if isinstance(conf, template.Template):
                target.update(conf.async_render(variables))
            else:
                target.update(template.render_complex(conf, variables))

            if CONF_ENTITY_ID in target:
                registry = entity_registry.async_get(hass)
                entity_ids = cv.comp_entity_ids_or_uuids(target[CONF_ENTITY_ID])
                if entity_ids not in (ENTITY_MATCH_ALL, ENTITY_MATCH_NONE):
                    entity_ids = entity_registry.async_validate_entity_ids(
                        registry, entity_ids
                    )
                target[CONF_ENTITY_ID] = entity_ids
        except TemplateError as ex:
            raise HomeAssistantError(
                f"Error rendering service target template: {ex}"
            ) from ex
        except vol.Invalid as ex:
            raise HomeAssistantError(
                f"Template rendered invalid entity IDs: {target[CONF_ENTITY_ID]}"
            ) from ex

    service_data = {}

    for conf in (CONF_SERVICE_DATA, CONF_SERVICE_DATA_TEMPLATE):
        if conf not in config:
            continue
        try:
            render = template.render_complex(config[conf], variables)
            if not isinstance(render, dict):
                raise HomeAssistantError(
                    "Error rendering data template: Result is not a Dictionary"
                )
            service_data.update(render)
        except TemplateError as ex:
            raise HomeAssistantError(f"Error rendering data template: {ex}") from ex

    if CONF_SERVICE_ENTITY_ID in config:
        if target:
            target[ATTR_ENTITY_ID] = config[CONF_SERVICE_ENTITY_ID]
        else:
            target = {ATTR_ENTITY_ID: config[CONF_SERVICE_ENTITY_ID]}

    return {
        "domain": domain,
        "service": service,
        "service_data": service_data,
        "target": target,
    }


@bind_hass
def extract_entity_ids(
    hass: HomeAssistant, service_call: ServiceCall, expand_group: bool = True
) -> set[str]:
    """Extract a list of entity ids from a service call.

    Will convert group entity ids to the entity ids it represents.
    """
    return asyncio.run_coroutine_threadsafe(
        async_extract_entity_ids(hass, service_call, expand_group), hass.loop
    ).result()


@bind_hass
async def async_extract_entities[_EntityT: Entity](
    hass: HomeAssistant,
    entities: Iterable[_EntityT],
    service_call: ServiceCall,
    expand_group: bool = True,
) -> list[_EntityT]:
    """Extract a list of entity objects from a service call.

    Will convert group entity ids to the entity ids it represents.
    """
    data_ent_id = service_call.data.get(ATTR_ENTITY_ID)

    if data_ent_id == ENTITY_MATCH_ALL:
        return [entity for entity in entities if entity.available]

    referenced = async_extract_referenced_entity_ids(hass, service_call, expand_group)
    combined = referenced.referenced | referenced.indirectly_referenced

    found = []

    for entity in entities:
        if entity.entity_id not in combined:
            continue

        combined.remove(entity.entity_id)

        if not entity.available:
            continue

        found.append(entity)

    referenced.log_missing(referenced.referenced & combined)

    return found


@bind_hass
async def async_extract_entity_ids(
    hass: HomeAssistant, service_call: ServiceCall, expand_group: bool = True
) -> set[str]:
    """Extract a set of entity ids from a service call.

    Will convert group entity ids to the entity ids it represents.
    """
    referenced = async_extract_referenced_entity_ids(hass, service_call, expand_group)
    return referenced.referenced | referenced.indirectly_referenced


def _has_match(ids: str | list[str] | None) -> TypeGuard[str | list[str]]:
    """Check if ids can match anything."""
    return ids not in (None, ENTITY_MATCH_NONE)


@bind_hass
def async_extract_referenced_entity_ids(  # noqa: C901
    hass: HomeAssistant, service_call: ServiceCall, expand_group: bool = True
) -> SelectedEntities:
    """Extract referenced entity IDs from a service call."""
    selector = ServiceTargetSelector(service_call)
    selected = SelectedEntities()

    if not selector.has_any_selector:
        return selected

    entity_ids: set[str] | list[str] = selector.entity_ids
    if expand_group:
        entity_ids = expand_entity_ids(hass, entity_ids)

    selected.referenced.update(entity_ids)

    if (
        not selector.device_ids
        and not selector.area_ids
        and not selector.floor_ids
        and not selector.label_ids
    ):
        return selected

    entities = entity_registry.async_get(hass).entities
    dev_reg = device_registry.async_get(hass)
    area_reg = area_registry.async_get(hass)

    if selector.floor_ids:
        floor_reg = floor_registry.async_get(hass)
        for floor_id in selector.floor_ids:
            if floor_id not in floor_reg.floors:
                selected.missing_floors.add(floor_id)

    for area_id in selector.area_ids:
        if area_id not in area_reg.areas:
            selected.missing_areas.add(area_id)

    for device_id in selector.device_ids:
        if device_id not in dev_reg.devices:
            selected.missing_devices.add(device_id)

    if selector.label_ids:
        label_reg = label_registry.async_get(hass)
        for label_id in selector.label_ids:
            if label_id not in label_reg.labels:
                selected.missing_labels.add(label_id)

            for entity_entry in entities.get_entries_for_label(label_id):
                if (
                    entity_entry.entity_category is None
                    and entity_entry.hidden_by is None
                ):
                    selected.indirectly_referenced.add(entity_entry.entity_id)

            for device_entry in dev_reg.devices.get_devices_for_label(label_id):
                selected.referenced_devices.add(device_entry.id)

            for area_entry in area_reg.areas.get_areas_for_label(label_id):
                selected.referenced_areas.add(area_entry.id)

    # Find areas for targeted floors
    if selector.floor_ids:
        selected.referenced_areas.update(
            area_entry.id
            for floor_id in selector.floor_ids
            for area_entry in area_reg.areas.get_areas_for_floor(floor_id)
        )

    selected.referenced_areas.update(selector.area_ids)
    selected.referenced_devices.update(selector.device_ids)

    if not selected.referenced_areas and not selected.referenced_devices:
        return selected

    # Add indirectly referenced by device
    selected.indirectly_referenced.update(
        entry.entity_id
        for device_id in selected.referenced_devices
        for entry in entities.get_entries_for_device_id(device_id)
        # Do not add entities which are hidden or which are config
        # or diagnostic entities.
        if (entry.entity_category is None and entry.hidden_by is None)
    )

    # Find devices for targeted areas
    referenced_devices_by_area: set[str] = set()
    if selected.referenced_areas:
        for area_id in selected.referenced_areas:
            referenced_devices_by_area.update(
                device_entry.id
                for device_entry in dev_reg.devices.get_devices_for_area_id(area_id)
            )
    selected.referenced_devices.update(referenced_devices_by_area)

    # Add indirectly referenced by area
    selected.indirectly_referenced.update(
        entry.entity_id
        for area_id in selected.referenced_areas
        # The entity's area matches a targeted area
        for entry in entities.get_entries_for_area_id(area_id)
        # Do not add entities which are hidden or which are config
        # or diagnostic entities.
        if entry.entity_category is None and entry.hidden_by is None
    )
    # Add indirectly referenced by area through device
    selected.indirectly_referenced.update(
        entry.entity_id
        for device_id in referenced_devices_by_area
        for entry in entities.get_entries_for_device_id(device_id)
        # Do not add entities which are hidden or which are config
        # or diagnostic entities.
        if (
            entry.entity_category is None
            and entry.hidden_by is None
            and (
                # The entity's device matches a device referenced
                # by an area and the entity
                # has no explicitly set area
                not entry.area_id
            )
        )
    )

    return selected


@bind_hass
async def async_extract_config_entry_ids(
    hass: HomeAssistant, service_call: ServiceCall, expand_group: bool = True
) -> set[str]:
    """Extract referenced config entry ids from a service call."""
    referenced = async_extract_referenced_entity_ids(hass, service_call, expand_group)
    ent_reg = entity_registry.async_get(hass)
    dev_reg = device_registry.async_get(hass)
    config_entry_ids: set[str] = set()

    # Some devices may have no entities
    for device_id in referenced.referenced_devices:
        if (
            device_id in dev_reg.devices
            and (device := dev_reg.async_get(device_id)) is not None
        ):
            config_entry_ids.update(device.config_entries)

    for entity_id in referenced.referenced | referenced.indirectly_referenced:
        entry = ent_reg.async_get(entity_id)
        if entry is not None and entry.config_entry_id is not None:
            config_entry_ids.add(entry.config_entry_id)

    return config_entry_ids


def _load_services_file(hass: HomeAssistant, integration: Integration) -> JSON_TYPE:
    """Load services file for an integration."""
    try:
        return cast(
            JSON_TYPE,
            _SERVICES_SCHEMA(
                load_yaml_dict(str(integration.file_path / "services.yaml"))
            ),
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Unable to find services.yaml for the %s integration", integration.domain
        )
        return {}
    except (HomeAssistantError, vol.Invalid) as ex:
        _LOGGER.warning(
            "Unable to parse services.yaml for the %s integration: %s",
            integration.domain,
            ex,
        )
        return {}


def _load_services_files(
    hass: HomeAssistant, integrations: Iterable[Integration]
) -> list[JSON_TYPE]:
    """Load service files for multiple integrations."""
    return [_load_services_file(hass, integration) for integration in integrations]


@callback
def async_get_cached_service_description(
    hass: HomeAssistant, domain: str, service: str
) -> dict[str, Any] | None:
    """Return the cached description for a service."""
    return hass.data.get(SERVICE_DESCRIPTION_CACHE, {}).get((domain, service))


@bind_hass
async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Return descriptions (i.e. user documentation) for all service calls."""
    descriptions_cache = hass.data.setdefault(SERVICE_DESCRIPTION_CACHE, {})

    # We don't mutate services here so we avoid calling
    # async_services which makes a copy of every services
    # dict.
    services = hass.services.async_services_internal()

    # See if there are new services not seen before.
    # Any service that we saw before already has an entry in description_cache.
    all_services = {
        (domain, service_name)
        for domain, services_by_domain in services.items()
        for service_name in services_by_domain
    }
    # If we have a complete cache, check if it is still valid
    all_cache: tuple[set[tuple[str, str]], dict[str, dict[str, Any]]] | None
    if all_cache := hass.data.get(ALL_SERVICE_DESCRIPTIONS_CACHE):
        previous_all_services, previous_descriptions_cache = all_cache
        # If the services are the same, we can return the cache
        if previous_all_services == all_services:
            return previous_descriptions_cache

    # Files we loaded for missing descriptions
    loaded: dict[str, JSON_TYPE] = {}
    # We try to avoid making a copy in the event the cache is good,
    # but now we must make a copy in case new services get added
    # while we are loading the missing ones so we do not
    # add the new ones to the cache without their descriptions
    services = {domain: service.copy() for domain, service in services.items()}

    if domains_with_missing_services := {
        domain for domain, _ in all_services.difference(descriptions_cache)
    }:
        ints_or_excs = await async_get_integrations(hass, domains_with_missing_services)
        integrations: list[Integration] = []
        for domain, int_or_exc in ints_or_excs.items():
            if type(int_or_exc) is Integration and int_or_exc.has_services:
                integrations.append(int_or_exc)
                continue
            if TYPE_CHECKING:
                assert isinstance(int_or_exc, Exception)
            _LOGGER.error("Failed to load integration: %s", domain, exc_info=int_or_exc)

        if integrations:
            contents = await hass.async_add_executor_job(
                _load_services_files, hass, integrations
            )
            loaded = dict(zip(domains_with_missing_services, contents, strict=False))

    # Load translations for all service domains
    translations = await translation.async_get_translations(
        hass, "en", "services", services
    )

    # Build response
    descriptions: dict[str, dict[str, Any]] = {}
    for domain, services_map in services.items():
        descriptions[domain] = {}
        domain_descriptions = descriptions[domain]

        for service_name, service in services_map.items():
            cache_key = (domain, service_name)
            description = descriptions_cache.get(cache_key)
            if description is not None:
                domain_descriptions[service_name] = description
                continue

            # Cache missing descriptions
            domain_yaml = loaded.get(domain) or {}
            # The YAML may be empty for dynamically defined
            # services (ie shell_command) that never call
            # service.async_set_service_schema for the dynamic
            # service

            yaml_description = (
                domain_yaml.get(service_name) or {}  # type: ignore[union-attr]
            )

            # Don't warn for missing services, because it triggers false
            # positives for things like scripts, that register as a service
            #
            # When name & description are in the translations use those;
            # otherwise fallback to backwards compatible behavior from
            # the time when we didn't have translations for descriptions yet.
            # This mimics the behavior of the frontend.
            description = {
                "name": translations.get(
                    f"component.{domain}.services.{service_name}.name",
                    yaml_description.get("name", ""),
                ),
                "description": translations.get(
                    f"component.{domain}.services.{service_name}.description",
                    yaml_description.get("description", ""),
                ),
                "fields": dict(yaml_description.get("fields", {})),
            }

            # Translate fields names & descriptions as well
            for field_name, field_schema in description["fields"].items():
                if name := translations.get(
                    f"component.{domain}.services.{service_name}.fields.{field_name}.name"
                ):
                    field_schema["name"] = name
                if desc := translations.get(
                    f"component.{domain}.services.{service_name}.fields.{field_name}.description"
                ):
                    field_schema["description"] = desc
                if example := translations.get(
                    f"component.{domain}.services.{service_name}.fields.{field_name}.example"
                ):
                    field_schema["example"] = example

            if "target" in yaml_description:
                description["target"] = yaml_description["target"]

            response = service.supports_response
            if response is not SupportsResponse.NONE:
                description["response"] = {
                    "optional": response is SupportsResponse.OPTIONAL,
                }

            descriptions_cache[cache_key] = description

            domain_descriptions[service_name] = description

    hass.data[ALL_SERVICE_DESCRIPTIONS_CACHE] = (all_services, descriptions)
    return descriptions


@callback
def remove_entity_service_fields(call: ServiceCall) -> dict[Any, Any]:
    """Remove entity service fields."""
    return {
        key: val
        for key, val in call.data.items()
        if key not in cv.ENTITY_SERVICE_FIELDS
    }


@callback
@bind_hass
def async_set_service_schema(
    hass: HomeAssistant, domain: str, service: str, schema: dict[str, Any]
) -> None:
    """Register a description for a service."""
    domain = domain.lower()
    service = service.lower()

    descriptions_cache = hass.data.setdefault(SERVICE_DESCRIPTION_CACHE, {})

    description = {
        "name": schema.get("name", ""),
        "description": schema.get("description", ""),
        "fields": schema.get("fields", {}),
    }

    if "target" in schema:
        description["target"] = schema["target"]

    if (
        response := hass.services.supports_response(domain, service)
    ) != SupportsResponse.NONE:
        description["response"] = {
            "optional": response == SupportsResponse.OPTIONAL,
        }

    hass.data.pop(ALL_SERVICE_DESCRIPTIONS_CACHE, None)
    descriptions_cache[(domain, service)] = description


def _get_permissible_entity_candidates(
    call: ServiceCall,
    entities: dict[str, Entity],
    entity_perms: Callable[[str, str], bool] | None,
    target_all_entities: bool,
    all_referenced: set[str] | None,
) -> list[Entity]:
    """Get entity candidates that the user is allowed to access."""
    if entity_perms is not None:
        # Check the permissions since entity_perms is set
        if target_all_entities:
            # If we target all entities, we will select all entities the user
            # is allowed to control.
            return [
                entity
                for entity_id, entity in entities.items()
                if entity_perms(entity_id, POLICY_CONTROL)
            ]

        assert all_referenced is not None
        # If they reference specific entities, we will check if they are all
        # allowed to be controlled.
        for entity_id in all_referenced:
            if not entity_perms(entity_id, POLICY_CONTROL):
                raise Unauthorized(
                    context=call.context,
                    entity_id=entity_id,
                    permission=POLICY_CONTROL,
                )

    elif target_all_entities:
        return list(entities.values())

    # We have already validated they have permissions to control all_referenced
    # entities so we do not need to check again.
    if TYPE_CHECKING:
        assert all_referenced is not None
    if (
        len(all_referenced) == 1
        and (single_entity := list(all_referenced)[0])
        and (entity := entities.get(single_entity)) is not None
    ):
        return [entity]

    return [entities[entity_id] for entity_id in all_referenced.intersection(entities)]


@bind_hass
async def entity_service_call(
    hass: HomeAssistant,
    registered_entities: dict[str, Entity],
    func: str | HassJob,
    call: ServiceCall,
    required_features: Iterable[int] | None = None,
) -> EntityServiceResponse | None:
    """Handle an entity service call.

    Calls all platforms simultaneously.
    """
    entity_perms: Callable[[str, str], bool] | None = None
    return_response = call.return_response

    if call.context.user_id:
        user = await hass.auth.async_get_user(call.context.user_id)
        if user is None:
            raise UnknownUser(context=call.context)
        if not user.is_admin:
            entity_perms = user.permissions.check_entity

    target_all_entities = call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL

    if target_all_entities:
        referenced: SelectedEntities | None = None
        all_referenced: set[str] | None = None
    else:
        # A set of entities we're trying to target.
        referenced = async_extract_referenced_entity_ids(hass, call, True)
        all_referenced = referenced.referenced | referenced.indirectly_referenced

    # If the service function is a string, we'll pass it the service call data
    if isinstance(func, str):
        data: dict | ServiceCall = remove_entity_service_fields(call)
    # If the service function is not a string, we pass the service call
    else:
        data = call

    # A list with entities to call the service on.
    entity_candidates = _get_permissible_entity_candidates(
        call,
        registered_entities,
        entity_perms,
        target_all_entities,
        all_referenced,
    )

    if not target_all_entities:
        assert referenced is not None
        # Only report on explicit referenced entities
        missing = referenced.referenced.copy()
        for entity in entity_candidates:
            missing.discard(entity.entity_id)
        referenced.log_missing(missing)

    entities: list[Entity] = []
    for entity in entity_candidates:
        if not entity.available:
            continue

        # Skip entities that don't have the required feature.
        if required_features is not None and (
            entity.supported_features is None
            or not any(
                entity.supported_features & feature_set == feature_set
                for feature_set in required_features
            )
        ):
            # If entity explicitly referenced, raise an error
            if referenced is not None and entity.entity_id in referenced.referenced:
                raise ServiceNotSupported(call.domain, call.service, entity.entity_id)

            continue

        entities.append(entity)

    if not entities:
        if return_response:
            raise HomeAssistantError(
                "Service call requested response data but did not match any entities"
            )
        return None

    if len(entities) == 1:
        # Single entity case avoids creating task
        entity = entities[0]
        single_response = await _handle_entity_call(
            hass, entity, func, data, call.context
        )
        if entity.should_poll:
            # Context expires if the turn on commands took a long time.
            # Set context again so it's there when we update
            entity.async_set_context(call.context)
            await entity.async_update_ha_state(True)
        return {entity.entity_id: single_response} if return_response else None

    # Use asyncio.gather here to ensure the returned results
    # are in the same order as the entities list
    results: list[ServiceResponse | BaseException] = await asyncio.gather(
        *[
            entity.async_request_call(
                _handle_entity_call(hass, entity, func, data, call.context)
            )
            for entity in entities
        ],
        return_exceptions=True,
    )

    response_data: EntityServiceResponse = {}
    for entity, result in zip(entities, results, strict=False):
        if isinstance(result, BaseException):
            raise result from None
        response_data[entity.entity_id] = result

    tasks: list[asyncio.Task[None]] = []

    for entity in entities:
        if not entity.should_poll:
            continue

        # Context expires if the turn on commands took a long time.
        # Set context again so it's there when we update
        entity.async_set_context(call.context)
        tasks.append(create_eager_task(entity.async_update_ha_state(True)))

    if tasks:
        done, pending = await asyncio.wait(tasks)
        assert not pending
        for future in done:
            future.result()  # pop exception if have

    return response_data if return_response and response_data else None


async def _handle_entity_call(
    hass: HomeAssistant,
    entity: Entity,
    func: str | HassJob,
    data: dict | ServiceCall,
    context: Context,
) -> ServiceResponse:
    """Handle calling service method."""
    entity.async_set_context(context)

    task: asyncio.Future[ServiceResponse] | None
    if isinstance(func, str):
        job = HassJob(
            partial(getattr(entity, func), **data),  # type: ignore[arg-type]
            job_type=entity.get_hassjob_type(func),
        )
        task = hass.async_run_hass_job(job)
    else:
        task = hass.async_run_hass_job(func, entity, data)

    # Guard because callback functions do not return a task when passed to
    # async_run_job.
    result: ServiceResponse = None
    if task is not None:
        result = await task

    if asyncio.iscoroutine(result):
        _LOGGER.error(  # type: ignore[unreachable]
            (
                "Service %s for %s incorrectly returns a coroutine object. Await result"
                " instead in service handler. Report bug to integration author"
            ),
            func,
            entity.entity_id,
        )
        result = await result

    return result


async def _async_admin_handler(
    hass: HomeAssistant,
    service_job: HassJob[[ServiceCall], Awaitable[None] | None],
    call: ServiceCall,
) -> None:
    """Run an admin service."""
    if call.context.user_id:
        user = await hass.auth.async_get_user(call.context.user_id)
        if user is None:
            raise UnknownUser(context=call.context)
        if not user.is_admin:
            raise Unauthorized(context=call.context)

    result = hass.async_run_hass_job(service_job, call)
    if result is not None:
        await result


@bind_hass
@callback
def async_register_admin_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    service_func: Callable[[ServiceCall], Awaitable[None] | None],
    schema: VolSchemaType = vol.Schema({}, extra=vol.PREVENT_EXTRA),
) -> None:
    """Register a service that requires admin access."""
    hass.services.async_register(
        domain,
        service,
        partial(
            _async_admin_handler,
            hass,
            HassJob(service_func, f"admin service {domain}.{service}"),
        ),
        schema,
    )


@bind_hass
@callback
def verify_domain_control(
    hass: HomeAssistant, domain: str
) -> Callable[[Callable[[ServiceCall], Any]], Callable[[ServiceCall], Any]]:
    """Ensure permission to access any entity under domain in service call."""

    def decorator(
        service_handler: Callable[[ServiceCall], Any],
    ) -> Callable[[ServiceCall], Any]:
        """Decorate."""
        if not asyncio.iscoroutinefunction(service_handler):
            raise HomeAssistantError("Can only decorate async functions.")

        async def check_permissions(call: ServiceCall) -> Any:
            """Check user permission and raise before call if unauthorized."""
            if not call.context.user_id:
                return await service_handler(call)

            user = await hass.auth.async_get_user(call.context.user_id)

            if user is None:
                raise UnknownUser(
                    context=call.context,
                    permission=POLICY_CONTROL,
                    user_id=call.context.user_id,
                )

            reg = entity_registry.async_get(hass)

            authorized = False

            for entity in reg.entities.values():
                if entity.platform != domain:
                    continue

                if user.permissions.check_entity(entity.entity_id, POLICY_CONTROL):
                    authorized = True
                    break

            if not authorized:
                raise Unauthorized(
                    context=call.context,
                    permission=POLICY_CONTROL,
                    user_id=call.context.user_id,
                    perm_category=CAT_ENTITIES,
                )

            return await service_handler(call)

        return check_permissions

    return decorator


class ReloadServiceHelper[_T]:
    """Helper for reload services.

    The helper has the following purposes:
    - Make sure reloads do not happen in parallel
    - Avoid redundant reloads of the same target
    """

    def __init__(
        self,
        service_func: Callable[[ServiceCall], Coroutine[Any, Any, Any]],
        reload_targets_func: Callable[[ServiceCall], set[_T]],
    ) -> None:
        """Initialize ReloadServiceHelper."""
        self._service_func = service_func
        self._service_running = False
        self._service_condition = asyncio.Condition()
        self._pending_reload_targets: set[_T] = set()
        self._reload_targets_func = reload_targets_func

    async def execute_service(self, service_call: ServiceCall) -> None:
        """Execute the service.

        If a previous reload task is currently in progress, wait for it to finish first.
        Once the previous reload task has finished, one of the waiting tasks will be
        assigned to execute the reload of the targets it is assigned to reload. The
        other tasks will wait if they should reload the same target, otherwise they
        will wait for the next round.
        """

        do_reload = False
        reload_targets = None
        async with self._service_condition:
            if self._service_running:
                # A previous reload task is already in progress, wait for it to finish,
                # because that task may be reloading a stale version of the resource.
                await self._service_condition.wait()

        while True:
            async with self._service_condition:
                # Once we've passed this point, we assume the version of the resource is
                # the one our task was assigned to reload, or a newer one. Regardless of
                # which, our task is happy as long as the target is reloaded at least
                # once.
                if reload_targets is None:
                    reload_targets = self._reload_targets_func(service_call)
                    self._pending_reload_targets |= reload_targets
                if not self._service_running:
                    # This task will do a reload
                    self._service_running = True
                    do_reload = True
                    break
                # Another task will perform a reload, wait for it to finish
                await self._service_condition.wait()
                # Check if the reload this task is waiting for has been completed
                if reload_targets.isdisjoint(self._pending_reload_targets):
                    break

        if do_reload:
            # Reload, then notify other tasks
            await self._service_func(service_call)
            async with self._service_condition:
                self._service_running = False
                self._pending_reload_targets -= reload_targets
                self._service_condition.notify_all()


@callback
def async_register_entity_service(
    hass: HomeAssistant,
    domain: str,
    name: str,
    *,
    entities: dict[str, Entity],
    func: str | Callable[..., Any],
    job_type: HassJobType | None,
    required_features: Iterable[int] | None = None,
    schema: VolDictType | VolSchemaType | None,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> None:
    """Help registering an entity service.

    This is called by EntityComponent.async_register_entity_service and
    EntityPlatform.async_register_entity_service and should not be called
    directly by integrations.
    """
    if schema is None or isinstance(schema, dict):
        schema = cv.make_entity_service_schema(schema)
    elif not cv.is_entity_service_schema(schema):
        # pylint: disable-next=import-outside-toplevel
        from .frame import ReportBehavior, report_usage

        report_usage(
            "registers an entity service with a non entity service schema",
            core_behavior=ReportBehavior.LOG,
            breaks_in_ha_version="2025.9",
        )

    service_func: str | HassJob[..., Any]
    service_func = func if isinstance(func, str) else HassJob(func)

    hass.services.async_register(
        domain,
        name,
        partial(
            entity_service_call,
            hass,
            entities,
            service_func,
            required_features=required_features,
        ),
        schema,
        supports_response,
        job_type=job_type,
    )
