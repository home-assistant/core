"""Service calling related helpers."""

import asyncio
from collections.abc import Callable, Coroutine, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from functools import cache, partial
import inspect
import logging
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast, overload

import probatio

from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_CONTROL
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ACTION,
    CONF_ENTITY_ID,
    CONF_EXCLUDE,
    CONF_SELECTOR,
    CONF_SERVICE_DATA,
    CONF_SERVICE_DATA_TEMPLATE,
    CONF_SERVICE_TEMPLATE,
    CONF_TARGET,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Context,
    EntityServiceResponse,
    Event,
    HassJob,
    HassJobType,
    HomeAssistant,
    Service,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotSupported,
    ServiceValidationError,
    TemplateError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.loader import Integration, async_get_integrations
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.yaml import load_yaml_dict

from . import (
    config_validation as cv,
    device_registry,
    entity_registry,
    selector,
    target as target_helpers,
    template,
)
from .selector import TargetSelector
from .typing import ConfigType, TemplateVarsType, VolDictType, VolSchemaType

if TYPE_CHECKING:
    from .entity import Entity

CONF_SERVICE_ENTITY_ID = "entity_id"

_LOGGER = logging.getLogger(__name__)

YAML_SERVICE_DESCRIPTIONS_CACHE: HassKey[dict[str, dict[str, dict[str, Any]]]] = (
    HassKey("yaml_service_descriptions_cache")
)
SERVICE_DESCRIPTION_CACHE: HassKey[dict[tuple[str, str], dict[str, Any] | None]] = (
    HassKey("service_description_cache")
)
REGISTERED_SERVICE_DESCRIPTIONS_CACHE: HassKey[
    tuple[set[tuple[str, str]], dict[str, dict[str, Any]]]
] = HassKey("registered_service_descriptions_cache")
ALL_SERVICE_DESCRIPTIONS_CACHE: HassKey[
    tuple[
        dict[str, dict[str, Any]],
        dict[str, dict[str, dict[str, Any]]],
        dict[str, dict[str, Any]],
    ]
] = HassKey("all_service_descriptions_cache")

type ServiceEventListener = Callable[
    [dict[str, dict[str, Any]], dict[str, set[str]]], Coroutine[Any, Any, None]
]


@dataclass(slots=True)
class _ServiceEventState:
    """State of the service description event subscriptions."""

    listeners: list[ServiceEventListener] = field(default_factory=list)
    awaiting_snapshot: list[ServiceEventListener] = field(default_factory=list)
    last_descriptions: dict[str, dict[str, Any]] | None = None
    dirty: bool = False
    running: bool = False


SERVICE_EVENT_STATE: HassKey[_ServiceEventState] = HassKey("service_event_state")


@cache
def _base_components() -> dict[str, ModuleType]:
    """Return a cached lookup of base components."""
    from homeassistant.components import (  # noqa: PLC0415
        ai_task,
        alarm_control_panel,
        assist_satellite,
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
        "ai_task": ai_task,
        "alarm_control_panel": alarm_control_panel,
        "assist_satellite": assist_satellite,
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
        raise probatio.Invalid(
            f"Invalid {label} '{option_or_feature}', expected <domain>.<enum>.<member>"
        ) from exc

    base_components = _base_components()
    if not (base_component := base_components.get(domain)):
        raise probatio.Invalid(f"Unknown base component '{domain}'")

    try:
        attribute_enum = getattr(base_component, enum)
    except AttributeError as exc:
        raise probatio.Invalid(f"Unknown {label} enum '{domain}.{enum}'") from exc

    if not issubclass(attribute_enum, Enum):
        raise probatio.Invalid(f"Expected {label} '{domain}.{enum}' to be an enum")

    try:
        return getattr(attribute_enum, option).value
    except AttributeError as exc:
        raise probatio.Invalid(f"Unknown {label} '{enum}.{option}'") from exc


def validate_attribute_option(attribute_option: str) -> Any:
    """Validate attribute option."""
    return _validate_option_or_feature(attribute_option, "attribute option")


def validate_supported_feature(supported_feature: str) -> Any:
    """Validate supported feature."""
    return _validate_option_or_feature(supported_feature, "supported feature")


# Basic schemas which translate attribute and supported feature enum names
# to their values. Full validation is done by hassfest.services
_FIELD_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_SELECTOR): selector.validate_selector,
        probatio.Optional("filter"): {
            probatio.Optional("attribute"): {
                probatio.Required(str): [probatio.All(str, validate_attribute_option)],
            },
            probatio.Optional("supported_features"): [
                probatio.All(str, validate_supported_feature)
            ],
        },
    },
    extra=probatio.ALLOW_EXTRA,
)

_SECTION_SCHEMA = probatio.Schema(
    {
        probatio.Required("fields"): probatio.Schema({str: _FIELD_SCHEMA}),
    },
    extra=probatio.ALLOW_EXTRA,
)

_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Optional("target"): TargetSelector.CONFIG_SCHEMA,
        probatio.Optional("fields"): probatio.Schema(
            {str: probatio.Any(_SECTION_SCHEMA, _FIELD_SCHEMA)}
        ),
    },
    extra=probatio.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise probatio.Invalid("Key does not start with .")
    return key


_SERVICES_SCHEMA = probatio.Schema(
    {
        probatio.Remove(probatio.All(str, starts_with_dot)): object,
        cv.slug: probatio.Any(None, _SERVICE_SCHEMA),
    }
)


class ServiceParams(TypedDict):
    """Type for service call parameters."""

    domain: str
    service: str
    service_data: dict[str, Any]
    target: dict | None


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
        except probatio.Invalid as ex:
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
        except probatio.Invalid as ex:
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
        except probatio.Invalid as ex:
            raise HomeAssistantError(
                f"Template rendered invalid entity IDs: {target[CONF_ENTITY_ID]}"
            ) from ex

        if exclude := target.get(CONF_EXCLUDE):
            try:
                target[CONF_EXCLUDE] = cv.TARGET_EXCLUDE_SCHEMA(exclude)
            except probatio.Invalid as ex:
                raise HomeAssistantError(
                    f"Template rendered invalid exclude block: {exclude}"
                ) from ex

    service_data = {}

    for conf in (CONF_SERVICE_DATA, CONF_SERVICE_DATA_TEMPLATE):
        if conf not in config:
            continue
        try:
            render = template.render_complex(config[conf], variables)
            if not isinstance(render, dict):
                raise HomeAssistantError(
                    translation_domain=HOMEASSISTANT_DOMAIN,
                    translation_key="service_data_template_not_dict",
                )
            service_data.update(render)
        except TemplateError as ex:
            raise HomeAssistantError(
                translation_domain=HOMEASSISTANT_DOMAIN,
                translation_key="service_data_template_error",
                translation_placeholders={"error": str(ex)},
            ) from ex

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


def extract_entity_ids(
    service_call: ServiceCall, expand_group: bool = True
) -> set[str]:
    """Extract a list of entity ids from a service call.

    Will convert group entity ids to the entity ids it represents.
    """
    return asyncio.run_coroutine_threadsafe(
        async_extract_entity_ids(service_call, expand_group), service_call.hass.loop
    ).result()


async def async_extract_entities[_EntityT: Entity](
    entities: Iterable[_EntityT],
    service_call: ServiceCall,
    expand_group: bool = True,
) -> list[_EntityT]:
    """Extract a list of entity objects from a service call.

    Will convert group entity ids to the entity ids it represents.
    """
    data_ent_id = service_call.data.get(ATTR_ENTITY_ID)

    target_selection = target_helpers.TargetSelection(service_call.data)

    if data_ent_id == ENTITY_MATCH_ALL:
        excluded = target_helpers.async_extract_excluded_entity_ids(
            service_call.hass, target_selection, expand_group
        )
        return [
            entity
            for entity in entities
            if entity.available and entity.entity_id not in excluded
        ]

    referenced = target_helpers.async_extract_referenced_entity_ids(
        service_call.hass, target_selection, expand_group
    )
    combined = referenced.referenced | referenced.indirectly_referenced

    found = []

    for entity in entities:
        if entity.entity_id not in combined:
            continue

        combined.remove(entity.entity_id)

        if not entity.available:
            continue

        found.append(entity)

    referenced.log_missing(referenced.referenced & combined, _LOGGER)

    return found


async def async_extract_entity_ids(
    service_call: ServiceCall, expand_group: bool = True
) -> set[str]:
    """Extract a set of entity ids from a service call.

    Will convert group entity ids to the entity ids it represents.
    """
    target_selection = target_helpers.TargetSelection(service_call.data)
    referenced = target_helpers.async_extract_referenced_entity_ids(
        service_call.hass, target_selection, expand_group
    )
    return referenced.referenced | referenced.indirectly_referenced


async def async_extract_config_entry_ids(
    service_call: ServiceCall, expand_group: bool = True
) -> set[str]:
    """Extract referenced config entry ids from a service call."""
    target_selection = target_helpers.TargetSelection(service_call.data)
    referenced = target_helpers.async_extract_referenced_entity_ids(
        service_call.hass, target_selection, expand_group
    )
    ent_reg = entity_registry.async_get(service_call.hass)
    dev_reg = device_registry.async_get(service_call.hass)
    config_entry_ids: set[str] = set()

    # Some devices may have no entities
    for device_id in referenced.referenced_devices:
        if (
            device := dev_reg.async_get(device_id, include_composite_devices=False)
        ) is not None:
            config_entry_ids.add(device.config_entry_id)

    for entity_id in referenced.referenced | referenced.indirectly_referenced:
        entry = ent_reg.async_get(entity_id)
        if entry is not None and entry.config_entry_id is not None:
            config_entry_ids.add(entry.config_entry_id)

    return config_entry_ids


def _load_services_file(integration: Integration) -> dict[str, Any]:
    """Load services file for an integration."""
    try:
        return cast(
            dict[str, Any],
            _SERVICES_SCHEMA(
                load_yaml_dict(str(integration.file_path / "services.yaml"))
            ),
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Unable to find services.yaml for the %s integration", integration.domain
        )
        return {}
    except (HomeAssistantError, probatio.Invalid) as ex:
        _LOGGER.warning(
            "Unable to parse services.yaml for the %s integration: %s",
            integration.domain,
            ex,
        )
        return {}


def _load_services_files(
    integrations: Iterable[Integration],
) -> dict[str, dict[str, Any]]:
    """Load service files for multiple integrations."""
    return {
        integration.domain: _load_services_file(integration)
        for integration in integrations
    }


@callback
def async_get_cached_service_description(
    hass: HomeAssistant, domain: str, service: str
) -> dict[str, Any] | None:
    """Return the cached description for a service."""
    return hass.data.get(SERVICE_DESCRIPTION_CACHE, {}).get((domain, service))


def _build_description(yaml_description: dict[str, Any] | None) -> dict[str, Any]:
    """Build the description of a service from its YAML."""
    if yaml_description is None:
        yaml_description = {}
    description: dict[str, Any] = {"fields": yaml_description.get("fields", {})}
    for item in ("description", "name", "target"):
        if item in yaml_description:
            description[item] = yaml_description[item]
    description["response"] = None
    description["description_placeholders"] = None
    return description


def _add_registration(description: dict[str, Any], service: Service) -> dict[str, Any]:
    """Return the description completed with what the registration knows."""
    description = {
        key: value for key, value in description.items() if value is not None
    }
    response = service.supports_response
    if response is not SupportsResponse.NONE:
        description["response"] = {"optional": response is SupportsResponse.OPTIONAL}
    if (placeholders := service.description_placeholders) is not None:
        description["description_placeholders"] = placeholders
    return description


async def _async_load_services_yaml(hass: HomeAssistant, domains: set[str]) -> None:
    """Load and cache the services.yaml of the domains not cached yet."""
    yaml_descriptions = hass.data.setdefault(YAML_SERVICE_DESCRIPTIONS_CACHE, {})
    if not (domains := domains.difference(yaml_descriptions)):
        return

    ints_or_excs = await async_get_integrations(hass, domains)
    integrations: list[Integration] = []
    loaded: dict[str, dict[str, Any]] = {}
    for domain, int_or_exc in ints_or_excs.items():
        if type(int_or_exc) is Integration and int_or_exc.has_services:
            integrations.append(int_or_exc)
            continue
        _LOGGER.error(
            "Failed to load services.yaml for integration: %s",
            domain,
            exc_info=None if isinstance(int_or_exc, Integration) else int_or_exc,
        )
        loaded[domain] = {}

    if integrations:
        loaded.update(
            await hass.async_add_executor_job(_load_services_files, integrations)
        )

    # Replace instead of mutating so caches can compare the dict identity
    yaml_descriptions = hass.data[YAML_SERVICE_DESCRIPTIONS_CACHE]
    hass.data[YAML_SERVICE_DESCRIPTIONS_CACHE] = {
        **yaml_descriptions,
        **{
            domain: {
                service: _build_description(yaml_description)
                for service, yaml_description in domain_yaml.items()
            }
            for domain, domain_yaml in loaded.items()
        },
    }


async def _async_get_registered_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Return descriptions for all registered services."""
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
    if (all_cache := hass.data.get(REGISTERED_SERVICE_DESCRIPTIONS_CACHE)) is not None:
        previous_all_services, previous_descriptions_cache = all_cache
        # If the services are the same, we can return the cache
        if previous_all_services == all_services:
            return previous_descriptions_cache

    # We try to avoid making a copy in the event the cache is good,
    # but now we must make a copy in case new services get added
    # while we are loading the missing ones so we do not
    # add the new ones to the cache without their descriptions
    services = {domain: service.copy() for domain, service in services.items()}

    if missing := all_services.difference(descriptions_cache):
        await _async_load_services_yaml(hass, {domain for domain, _ in missing})
        yaml_descriptions = hass.data[YAML_SERVICE_DESCRIPTIONS_CACHE]
        for domain, service_name in missing:
            cache_key = (domain, service_name)
            # The description may have been set while loading
            if cache_key in descriptions_cache:
                continue
            # The YAML may not describe dynamically defined services
            # (e.g. shell_command) that never call async_set_service_schema
            yaml_description = yaml_descriptions[domain].get(service_name)
            if yaml_description is None:
                yaml_description = _build_description(None)
            descriptions_cache[cache_key] = _add_registration(
                yaml_description, services[domain][service_name]
            )

    descriptions: dict[str, dict[str, Any]] = {
        domain: {
            service_name: descriptions_cache[(domain, service_name)]
            for service_name in services_map
        }
        for domain, services_map in services.items()
    }

    hass.data[REGISTERED_SERVICE_DESCRIPTIONS_CACHE] = (all_services, descriptions)
    return descriptions


async def async_get_all_descriptions(
    hass: HomeAssistant, *, registered_only: bool = True
) -> dict[str, dict[str, Any]]:
    """Return descriptions for all services.

    With registered_only False, all services in a loaded services.yaml are
    included, already registered or not.
    """
    registered_descriptions = await _async_get_registered_descriptions(hass)
    if registered_only:
        return registered_descriptions

    yaml_descriptions = hass.data.setdefault(YAML_SERVICE_DESCRIPTIONS_CACHE, {})
    if (all_cache := hass.data.get(ALL_SERVICE_DESCRIPTIONS_CACHE)) is not None:
        cached_registered_descriptions, cached_yaml_descriptions, all_descriptions = (
            all_cache
        )
        if (
            cached_registered_descriptions is registered_descriptions
            and cached_yaml_descriptions is yaml_descriptions
        ):
            return all_descriptions

    descriptions_cache = hass.data[SERVICE_DESCRIPTION_CACHE]
    all_descriptions = {
        domain: domain_descriptions.copy()
        for domain, domain_descriptions in registered_descriptions.items()
    }
    for domain, domain_yaml_descriptions in yaml_descriptions.items():
        if not domain_yaml_descriptions:
            continue
        domain_descriptions = all_descriptions.setdefault(domain, {})
        for service_name, yaml_description in domain_yaml_descriptions.items():
            if service_name in domain_descriptions:
                continue
            # A service that was registered before keeps what was learnt then
            registered_description = descriptions_cache.get((domain, service_name))
            domain_descriptions[service_name] = (
                yaml_description
                if registered_description is None
                else registered_description
            )

    hass.data[ALL_SERVICE_DESCRIPTIONS_CACHE] = (
        registered_descriptions,
        yaml_descriptions,
        all_descriptions,
    )
    return all_descriptions


@callback
def async_subscribe_service_events(
    hass: HomeAssistant, on_event: ServiceEventListener
) -> CALLBACK_TYPE:
    """Subscribe to the service descriptions.

    The listener first gets all descriptions, then the changed descriptions
    and the removed services, by domain.
    """
    if (event_state := hass.data.get(SERVICE_EVENT_STATE)) is None:
        event_state = hass.data[SERVICE_EVENT_STATE] = _ServiceEventState()

        @callback
        def _schedule(_: Event) -> None:
            _async_schedule_service_events(hass)

        hass.bus.async_listen(EVENT_SERVICE_REGISTERED, _schedule)
        hass.bus.async_listen(EVENT_SERVICE_REMOVED, _schedule)

    event_state.listeners.append(on_event)
    event_state.awaiting_snapshot.append(on_event)
    _async_schedule_service_events(hass)

    def remove_subscription() -> None:
        event_state.listeners.remove(on_event)
        if on_event in event_state.awaiting_snapshot:
            event_state.awaiting_snapshot.remove(on_event)

    return remove_subscription


@callback
def _async_schedule_service_events(hass: HomeAssistant) -> None:
    """Deliver the service description changes to the listeners, coalescing bursts."""
    if (
        event_state := hass.data.get(SERVICE_EVENT_STATE)
    ) is None or not event_state.listeners:
        return
    event_state.dirty = True
    if event_state.running:
        return
    event_state.running = True
    hass.async_create_task(
        _async_notify_service_events(hass), "service events", eager_start=False
    )


async def _async_notify_service_events(hass: HomeAssistant) -> None:
    """Send the listeners the difference since the descriptions last sent."""
    event_state = hass.data[SERVICE_EVENT_STATE]
    while event_state.dirty:
        event_state.dirty = False
        descriptions = await async_get_all_descriptions(hass, registered_only=False)
        last_descriptions = event_state.last_descriptions
        event_state.last_descriptions = descriptions

        changed: dict[str, dict[str, Any]] = {}
        removed: dict[str, set[str]] = {}
        if last_descriptions is not None:
            for domain, domain_descriptions in descriptions.items():
                last_domain_descriptions = last_descriptions.get(domain, {})
                if domain_changed := {
                    service: description
                    for service, description in domain_descriptions.items()
                    if last_domain_descriptions.get(service) is not description
                }:
                    changed[domain] = domain_changed
            for domain, last_domain_descriptions in last_descriptions.items():
                if domain_removed := set(last_domain_descriptions).difference(
                    descriptions.get(domain, {})
                ):
                    removed[domain] = domain_removed

        awaiting_snapshot = event_state.awaiting_snapshot
        event_state.awaiting_snapshot = []
        no_removed: dict[str, set[str]] = {}
        for listener in event_state.listeners.copy():
            try:
                if listener in awaiting_snapshot:
                    await listener(descriptions, no_removed)
                elif changed or removed:
                    await listener(changed, removed)
            except Exception:
                _LOGGER.exception("Error while notifying service event listener")
    event_state.running = False


async def async_declare_service(hass: HomeAssistant, service: str) -> None:
    """Ensure a referenced service is described even if it is not registered."""
    await _async_load_services_yaml(hass, {service.split(".", 1)[0]})
    _async_schedule_service_events(hass)


@callback
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
        # Match validation applied to descriptions loaded from services.yaml.
        try:
            description["target"] = TargetSelector.CONFIG_SCHEMA(schema["target"])
        except probatio.Invalid as err:
            _LOGGER.warning(
                "Invalid target in the description of service %s.%s, ignoring it: %s",
                domain,
                service,
                err,
            )

    if (
        response := hass.services.supports_response(domain, service)
    ) != SupportsResponse.NONE:
        description["response"] = {
            "optional": response == SupportsResponse.OPTIONAL,
        }

    hass.data.pop(REGISTERED_SERVICE_DESCRIPTIONS_CACHE, None)
    descriptions_cache[(domain, service)] = description
    _async_schedule_service_events(hass)


@callback
def remove_entity_service_fields(call: ServiceCall) -> dict[Any, Any]:
    """Remove entity service fields."""
    return {
        key: val
        for key, val in call.data.items()
        if key not in cv.ENTITY_SERVICE_FIELDS
    }


def _get_permissible_entity_candidates(
    call: ServiceCall,
    entities: Mapping[str, Entity],
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


async def _resolve_entity_service_call_entities(
    hass: HomeAssistant,
    registered_entities: Mapping[str, Entity] | Callable[[], Mapping[str, Entity]],
    call: ServiceCall,
    required_features: Iterable[int] | None = None,
    entity_device_classes: Iterable[str | None] | None = None,
    admin_only: bool = False,
) -> list[Entity] | None:
    """Resolve and filter entities for an entity service call."""
    entity_perms: Callable[[str, str], bool] | None = None

    if call.context.user_id:
        user = await hass.auth.async_get_user(call.context.user_id)
        if user is None:
            raise UnknownUser(context=call.context)
        if not user.is_admin:
            if admin_only:
                raise Unauthorized(context=call.context)
            entity_perms = user.permissions.check_entity

    target_all_entities = call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL

    if target_all_entities:
        referenced: target_helpers.SelectedEntities | None = None
        all_referenced: set[str] | None = None
    else:
        # A set of entities we're trying to target.
        target_selection = target_helpers.TargetSelection(call.data)
        referenced = target_helpers.async_extract_referenced_entity_ids(
            hass, target_selection, True
        )
        all_referenced = referenced.referenced | referenced.indirectly_referenced

    if callable(registered_entities):
        _registered_entities = registered_entities()
    else:
        _registered_entities = registered_entities

    # A list with entities to call the service on.
    entity_candidates = _get_permissible_entity_candidates(
        call,
        _registered_entities,
        entity_perms,
        target_all_entities,
        all_referenced,
    )

    entity_candidates = [e for e in entity_candidates if e.available]

    if target_all_entities and (
        excluded := target_helpers.async_extract_excluded_entity_ids(
            hass, target_helpers.TargetSelection(call.data)
        )
    ):
        entity_candidates = [
            e for e in entity_candidates if e.entity_id not in excluded
        ]

    if not target_all_entities:
        assert referenced is not None
        # Only report on explicit referenced entities
        missing = referenced.referenced.copy()
        for entity in entity_candidates:
            missing.discard(entity.entity_id)
        referenced.log_missing(missing, _LOGGER)

    entities: list[Entity] = []
    for entity in entity_candidates:
        # Skip entities that don't have the required device class.
        if (
            entity_device_classes is not None
            and entity.device_class not in entity_device_classes
        ):
            # If entity explicitly referenced, raise an error
            if referenced is not None and entity.entity_id in referenced.referenced:
                raise ServiceNotSupported(call.domain, call.service, entity.entity_id)

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
        if call.return_response:
            raise HomeAssistantError(
                "Service call requested response data but did not match any entities"
            )
        return None

    return entities


async def _async_handle_entity_calls(
    entity_calls: list[tuple[Entity, Coroutine[Any, Any, ServiceResponse]]],
    *,
    context: Context,
) -> EntityServiceResponse:
    """Handle calls for entities."""

    async def _with_context(
        entity: Entity, coro: Coroutine[Any, Any, ServiceResponse]
    ) -> ServiceResponse:
        entity.async_set_context(context)
        return await coro

    if len(entity_calls) == 1:
        # Single entity case avoids creating task
        entity, coro = entity_calls[0]
        single_result = await entity.async_request_call(_with_context(entity, coro))
        if entity.should_poll:
            # Context can expire, so set it again before we update
            entity.async_set_context(context)
            await entity.async_update_ha_state(True)
        return {entity.entity_id: single_result}

    entities = [entity for entity, _ in entity_calls]
    results: list[ServiceResponse | BaseException] = await asyncio.gather(
        *[
            entity.async_request_call(_with_context(entity, coro))
            for entity, coro in entity_calls
        ],
        return_exceptions=True,
    )

    response_data: EntityServiceResponse = {}
    for entity, result in zip(entities, results, strict=True):
        if isinstance(result, BaseException):
            raise result from None
        response_data[entity.entity_id] = result

    tasks: list[asyncio.Task[None]] = []
    for entity in entities:
        if not entity.should_poll:
            continue
        # Context can expire, so set it again before we update
        entity.async_set_context(context)
        tasks.append(create_eager_task(entity.async_update_ha_state(True)))

    if tasks:
        done, pending = await asyncio.wait(tasks)
        assert not pending
        for future in done:
            future.result()

    return response_data


async def async_handle_entity_calls(
    func: str,
    entity_data: Sequence[tuple[Entity, dict[str, Any]]],
    *,
    context: Context,
) -> EntityServiceResponse:
    """Handle calls for multiple entities."""
    return await _async_handle_entity_calls(
        [
            (
                entity,
                getattr(entity, func)(**data),
            )
            for entity, data in entity_data
        ],
        context=context,
    )


async def _handle_single_entity_call(
    hass: HomeAssistant,
    entity: Entity,
    func: str | HassJob,
    data: dict | ServiceCall,
) -> ServiceResponse:
    """Handle calling service method."""
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


async def entity_service_call(
    hass: HomeAssistant,
    registered_entities: Mapping[str, Entity] | Callable[[], Mapping[str, Entity]],
    func: str | HassJob,
    call: ServiceCall,
    required_features: Iterable[int] | None = None,
    *,
    admin_only: bool = False,
    entity_device_classes: Iterable[str | None] | None = None,
) -> EntityServiceResponse | None:
    """Handle an entity service call.

    Calls all platforms simultaneously.
    """
    entities = await _resolve_entity_service_call_entities(
        hass,
        registered_entities,
        call,
        required_features,
        entity_device_classes,
        admin_only=admin_only,
    )
    if entities is None:
        return None

    # If the service function is a string, we'll pass it the service call data
    if isinstance(func, str):
        data: dict | ServiceCall = remove_entity_service_fields(call)
    # If the service function is not a string, we pass the service call
    else:
        data = call

    response_data = await _async_handle_entity_calls(
        [
            (entity, _handle_single_entity_call(hass, entity, func, data))
            for entity in entities
        ],
        context=call.context,
    )

    return response_data if call.return_response else None


async def batched_entity_service_call(
    hass: HomeAssistant,
    registered_entities: Mapping[str, Entity] | Callable[[], Mapping[str, Entity]],
    func: Callable[
        [list[Entity], ServiceCall],
        Coroutine[Any, Any, EntityServiceResponse | None],
    ],
    call: ServiceCall,
    required_features: Iterable[int] | None = None,
) -> EntityServiceResponse | None:
    """Handle a batched entity service call.

    Calls the service function once with all matching entities as a list,
    instead of once per entity.
    """
    entities = await _resolve_entity_service_call_entities(
        hass, registered_entities, call, required_features
    )
    if entities is None:
        return None

    return_response = call.return_response

    # Create a new ServiceCall without entity service fields.
    call = ServiceCall(
        hass,
        call.domain,
        call.service,
        remove_entity_service_fields(call),
        context=call.context,
        return_response=return_response,
    )
    result = await func(entities, call)

    return result if return_response else None


async def _async_admin_handler(
    hass: HomeAssistant,
    service_job: HassJob[
        [ServiceCall],
        Coroutine[Any, Any, ServiceResponse | EntityServiceResponse]
        | ServiceResponse
        | EntityServiceResponse
        | None,
    ],
    call: ServiceCall,
) -> ServiceResponse | EntityServiceResponse | None:
    """Run an admin service."""
    if call.context.user_id:
        user = await hass.auth.async_get_user(call.context.user_id)
        if user is None:
            raise UnknownUser(context=call.context)
        if not user.is_admin:
            raise Unauthorized(context=call.context)

    task = hass.async_run_hass_job(service_job, call)
    if task is not None:
        return await task
    return None


@callback
def async_register_admin_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    service_func: Callable[
        [ServiceCall],
        Coroutine[Any, Any, ServiceResponse | EntityServiceResponse]
        | ServiceResponse
        | EntityServiceResponse
        | None,
    ],
    schema: VolSchemaType = probatio.Schema({}, extra=probatio.PREVENT_EXTRA),
    supports_response: SupportsResponse = SupportsResponse.NONE,
    *,
    description_placeholders: Mapping[str, str] | None = None,
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
        supports_response,
        description_placeholders=description_placeholders,
    )


@callback
def verify_domain_control(
    domain: str,
) -> Callable[[Callable[[ServiceCall], Any]], Callable[[ServiceCall], Any]]:
    """Ensure permission to access any entity under domain in service call."""

    def decorator(
        service_handler: Callable[[ServiceCall], Any],
    ) -> Callable[[ServiceCall], Any]:
        """Decorate."""
        if not inspect.iscoroutinefunction(service_handler):
            raise HomeAssistantError("Can only decorate async functions.")

        async def check_permissions(call: ServiceCall) -> Any:
            """Check user permission and raise before call if unauthorized."""
            if not call.context.user_id:
                return await service_handler(call)

            hass = call.hass
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
            try:
                await self._service_func(service_call)
            finally:
                async with self._service_condition:
                    self._service_running = False
                    self._pending_reload_targets -= reload_targets
                    self._service_condition.notify_all()


def _validate_entity_service_schema(
    schema: VolDictType | VolSchemaType | None, service: str
) -> VolSchemaType:
    """Validate that a schema is an entity service schema."""
    if schema is None or isinstance(schema, dict):
        return cv.make_entity_service_schema(schema)
    if not cv.is_entity_service_schema(schema):
        raise HomeAssistantError(
            f"The {service} service registers an entity service"
            " with a non entity service schema"
        )
    return schema


@callback
def async_register_entity_service(
    hass: HomeAssistant,
    domain: str,
    name: str,
    *,
    admin_only: bool = False,
    description_placeholders: Mapping[str, str] | None = None,
    entity_device_classes: Iterable[str | None] | None = None,
    entities: Mapping[str, Entity],
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
    schema = _validate_entity_service_schema(schema, f"{domain}.{name}")

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
            admin_only=admin_only,
            entity_device_classes=entity_device_classes,
            required_features=required_features,
        ),
        schema,
        supports_response,
        job_type=job_type,
        description_placeholders=description_placeholders,
    )


@callback
def async_register_batched_entity_service[_EntityT: Entity](
    hass: HomeAssistant,
    domain: str,
    name: str,
    *,
    description_placeholders: Mapping[str, str] | None = None,
    entities: dict[str, _EntityT],
    func: Callable[
        [list[_EntityT], ServiceCall],
        Coroutine[Any, Any, EntityServiceResponse | None],
    ],
    required_features: Iterable[int] | None = None,
    schema: VolDictType | VolSchemaType | None,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> None:
    """Help registering a batched entity service.

    This is called by EntityComponent.async_register_batched_entity_service
    and should not be called directly by integrations.

    A batched entity service calls the service function once with all
    matching entities as a list, instead of once per entity.
    """
    schema = _validate_entity_service_schema(schema, f"{domain}.{name}")

    hass.services.async_register(
        domain,
        name,
        partial(
            batched_entity_service_call,
            hass,
            entities,
            func,  # type: ignore[arg-type]
            required_features=required_features,
        ),
        schema,
        supports_response,
        job_type=HassJobType.Coroutinefunction,
        description_placeholders=description_placeholders,
    )


def _get_platform_entities(
    hass: HomeAssistant,
    entity_domain: str,
    service_domain: str,
) -> dict[str, Entity]:
    """Get platform entities for a service domain."""
    from .entity_platform import DATA_DOMAIN_PLATFORM_ENTITIES  # noqa: PLC0415

    entities = hass.data.get(DATA_DOMAIN_PLATFORM_ENTITIES, {}).get(
        (entity_domain, service_domain)
    )
    if entities is None:
        return {}
    return entities


@callback
def async_register_platform_entity_service(
    hass: HomeAssistant,
    service_domain: str,
    service_name: str,
    *,
    admin_only: bool = False,
    description_placeholders: Mapping[str, str] | None = None,
    entity_device_classes: Iterable[str | None] | None = None,
    entity_domain: str,
    func: str | Callable[..., Any],
    required_features: Iterable[int] | None = None,
    schema: VolDictType | VolSchemaType | None,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> None:
    """Help registering a platform entity service."""
    schema = _validate_entity_service_schema(schema, f"{service_domain}.{service_name}")

    service_func: str | HassJob[..., Any]
    service_func = func if isinstance(func, str) else HassJob(func)

    hass.services.async_register(
        service_domain,
        service_name,
        partial(
            entity_service_call,
            hass,
            partial(_get_platform_entities, hass, entity_domain, service_domain),
            service_func,
            admin_only=admin_only,
            entity_device_classes=entity_device_classes,
            required_features=required_features,
        ),
        schema,
        supports_response,
        job_type=HassJobType.Coroutinefunction,
        description_placeholders=description_placeholders,
    )


@callback
def async_register_batched_platform_entity_service[_EntityT: Entity](
    hass: HomeAssistant,
    service_domain: str,
    service_name: str,
    *,
    description_placeholders: Mapping[str, str] | None = None,
    entity_domain: str,
    func: Callable[
        [list[_EntityT], ServiceCall],
        Coroutine[Any, Any, EntityServiceResponse | None],
    ],
    required_features: Iterable[int] | None = None,
    schema: VolDictType | VolSchemaType | None,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> None:
    """Help registering a batched platform entity service.

    A batched entity service calls the service function once with all
    matching entities as a list, instead of once per entity.
    """
    schema = _validate_entity_service_schema(schema, f"{service_domain}.{service_name}")

    hass.services.async_register(
        service_domain,
        service_name,
        partial(
            batched_entity_service_call,
            hass,
            partial(_get_platform_entities, hass, entity_domain, service_domain),
            func,  # type: ignore[arg-type]
            required_features=required_features,
        ),
        schema,
        supports_response,
        job_type=HassJobType.Coroutinefunction,
        description_placeholders=description_placeholders,
    )


@callback
def async_get_config_entry(
    hass: HomeAssistant, domain: str, entry_id: str | None
) -> ConfigEntry:
    """Get and validate a service config entry."""
    if entry_id is None:
        return _async_get_single_loaded_config_entry(hass, domain)
    config_entry = hass.config_entries.async_get_entry(entry_id)
    if not config_entry:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_config_entry_not_found",
            translation_placeholders={
                "domain": domain,
                "entry_id": entry_id,
            },
        )
    if config_entry.domain != domain:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_config_entry_wrong_domain",
            translation_placeholders={
                "domain": domain,
                "entry_title": config_entry.title,
            },
        )
    if config_entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_config_entry_not_loaded",
            translation_placeholders={
                "domain": domain,
                "entry_title": config_entry.title,
            },
        )
    return config_entry


@callback
def _async_get_single_loaded_config_entry(
    hass: HomeAssistant, domain: str
) -> ConfigEntry:
    """Retrieve single loaded config entry.

    This is a fallback for services that do not request (or have not been
    provided with) a config entry ID. Only one config entry should exist
    for the domain, and it must be loaded.
    """
    config_entries = hass.config_entries.async_entries(
        domain, include_ignore=False, include_disabled=False
    )
    if not config_entries:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_found_no_config_entry_for_domain",
            translation_placeholders={"domain": domain},
        )
    if len(config_entries) > 1:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_found_multiple_config_entry_for_domain",
            translation_placeholders={"domain": domain},
        )
    config_entry = config_entries[0]
    if config_entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_config_entry_not_loaded",
            translation_placeholders={
                "domain": domain,
                "entry_title": config_entry.title,
            },
        )
    return config_entry


@overload
def async_get_device_and_config_entry(
    hass: HomeAssistant,
    domain: str,
    device_id: str,
    *,
    include_child_devices: Literal[False],
    include_main_devices: bool = True,
) -> tuple[device_registry.DeviceEntry, ConfigEntry]: ...


@overload
def async_get_device_and_config_entry(
    hass: HomeAssistant,
    domain: str,
    device_id: str,
    *,
    include_child_devices: Literal[True] = True,
    include_main_devices: Literal[False],
) -> tuple[device_registry.ChildDeviceEntry, ConfigEntry]: ...


@overload
def async_get_device_and_config_entry(
    hass: HomeAssistant,
    domain: str,
    device_id: str,
    *,
    include_child_devices: bool = True,
    include_main_devices: bool = True,
) -> tuple[device_registry.AnyDeviceEntry, ConfigEntry]: ...


@callback
def async_get_device_and_config_entry(
    hass: HomeAssistant,
    domain: str,
    device_id: str,
    *,
    include_child_devices: bool = True,
    include_main_devices: bool = True,
) -> tuple[device_registry.AnyDeviceEntry, ConfigEntry]:
    """Get and validate the device and the loaded config entry of the domain owning it.

    Raises ServiceValidationError if the device is unknown, is not owned by a
    config entry of the domain, or if that config entry is not loaded.

    With include_child_devices=False a child-device id raises as an unknown device.
    With include_main_devices=False a main-device id raises as an unknown device;
    as does a composite-device id, because both the splits of a composite and the
    restored composite itself are main devices.
    """
    device, config_entry = device_registry.async_get_device_and_config_entry_for_domain(
        hass,
        device_id,
        domain=domain,
        include_child_devices=include_child_devices,
        include_main_devices=include_main_devices,
    )
    if device is None:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_device_not_found",
            translation_placeholders={"device_id": device_id},
        )
    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_device_wrong_domain",
            translation_placeholders={
                "device_name": device.name_by_user or device.name or device_id,
                "domain": domain,
            },
        )
    if config_entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="service_config_entry_not_loaded",
            translation_placeholders={
                "domain": domain,
                "entry_title": config_entry.title,
            },
        )
    return device, config_entry
