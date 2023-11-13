"""Service calling related helpers."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
import dataclasses
from enum import Enum
from functools import cache, partial, wraps
import logging
from types import ModuleType
from typing import TYPE_CHECKING, Any, TypedDict, TypeGuard, TypeVar, cast

import voluptuous as vol

from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_CONTROL
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_SERVICE,
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
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    HomeAssistantError,
    TemplateError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.loader import Integration, async_get_integrations, bind_hass
from homeassistant.util.yaml import load_yaml
from homeassistant.util.yaml.loader import JSON_TYPE

from . import (
    area_registry,
    config_validation as cv,
    device_registry,
    entity_registry,
    template,
    translation,
)
from .selector import TargetSelector
from .typing import ConfigType, TemplateVarsType

if TYPE_CHECKING:
    from .entity import Entity
    from .entity_platform import EntityPlatform

    _EntityT = TypeVar("_EntityT", bound=Entity)


CONF_SERVICE_ENTITY_ID = "entity_id"

_LOGGER = logging.getLogger(__name__)

SERVICE_DESCRIPTION_CACHE = "service_description_cache"
ALL_SERVICE_DESCRIPTIONS_CACHE = "all_service_descriptions_cache"


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
        remote,
        siren,
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
        "remote": remote,
        "siren": siren,
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
            f"Invalid {label} '{option_or_feature}', expected "
            "<domain>.<enum>.<member>"
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

_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("target"): vol.Any(TargetSelector.CONFIG_SCHEMA, None),
        vol.Optional("fields"): vol.Schema({str: _FIELD_SCHEMA}),
    },
    extra=vol.ALLOW_EXTRA,
)

_SERVICES_SCHEMA = vol.Schema({cv.slug: vol.Any(None, _SERVICE_SCHEMA)})


class ServiceParams(TypedDict):
    """Type for service call parameters."""

    domain: str
    service: str
    service_data: dict[str, Any]
    target: dict | None


class ServiceTargetSelector:
    """Class to hold a target selector for a service."""

    def __init__(self, service_call: ServiceCall) -> None:
        """Extract ids from service call data."""
        entity_ids: str | list | None = service_call.data.get(ATTR_ENTITY_ID)
        device_ids: str | list | None = service_call.data.get(ATTR_DEVICE_ID)
        area_ids: str | list | None = service_call.data.get(ATTR_AREA_ID)

        self.entity_ids = (
            set(cv.ensure_list(entity_ids)) if _has_match(entity_ids) else set()
        )
        self.device_ids = (
            set(cv.ensure_list(device_ids)) if _has_match(device_ids) else set()
        )
        self.area_ids = set(cv.ensure_list(area_ids)) if _has_match(area_ids) else set()

    @property
    def has_any_selector(self) -> bool:
        """Determine if any selectors are present."""
        return bool(self.entity_ids or self.device_ids or self.area_ids)


@dataclasses.dataclass(slots=True)
class SelectedEntities:
    """Class to hold the selected entities."""

    # Entities that were explicitly mentioned.
    referenced: set[str] = dataclasses.field(default_factory=set)

    # Entities that were referenced via device/area ID.
    # Should not trigger a warning when they don't exist.
    indirectly_referenced: set[str] = dataclasses.field(default_factory=set)

    # Referenced items that could not be found.
    missing_devices: set[str] = dataclasses.field(default_factory=set)
    missing_areas: set[str] = dataclasses.field(default_factory=set)

    # Referenced devices
    referenced_devices: set[str] = dataclasses.field(default_factory=set)

    def log_missing(self, missing_entities: set[str]) -> None:
        """Log about missing items."""
        parts = []
        for label, items in (
            ("areas", self.missing_areas),
            ("devices", self.missing_devices),
            ("entities", missing_entities),
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

    if CONF_SERVICE in config:
        domain_service = config[CONF_SERVICE]
    else:
        domain_service = config[CONF_SERVICE_TEMPLATE]

    if isinstance(domain_service, template.Template):
        try:
            domain_service.hass = hass
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
                conf.hass = hass
                target.update(conf.async_render(variables))
            else:
                template.attach(hass, conf)
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
            template.attach(hass, config[conf])
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
async def async_extract_entities(
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
def async_extract_referenced_entity_ids(
    hass: HomeAssistant, service_call: ServiceCall, expand_group: bool = True
) -> SelectedEntities:
    """Extract referenced entity IDs from a service call."""
    selector = ServiceTargetSelector(service_call)
    selected = SelectedEntities()

    if not selector.has_any_selector:
        return selected

    entity_ids = selector.entity_ids
    if expand_group:
        entity_ids = hass.components.group.expand_entity_ids(entity_ids)

    selected.referenced.update(entity_ids)

    if not selector.device_ids and not selector.area_ids:
        return selected

    ent_reg = entity_registry.async_get(hass)
    dev_reg = device_registry.async_get(hass)
    area_reg = area_registry.async_get(hass)

    for device_id in selector.device_ids:
        if device_id not in dev_reg.devices:
            selected.missing_devices.add(device_id)

    for area_id in selector.area_ids:
        if area_id not in area_reg.areas:
            selected.missing_areas.add(area_id)

    # Find devices for targeted areas
    selected.referenced_devices.update(selector.device_ids)
    for device_entry in dev_reg.devices.values():
        if device_entry.area_id in selector.area_ids:
            selected.referenced_devices.add(device_entry.id)

    if not selector.area_ids and not selected.referenced_devices:
        return selected

    for ent_entry in ent_reg.entities.values():
        # Do not add entities which are hidden or which are config
        # or diagnostic entities.
        if ent_entry.entity_category is not None or ent_entry.hidden_by is not None:
            continue

        if (
            # The entity's area matches a targeted area
            ent_entry.area_id in selector.area_ids
            # The entity's device matches a device referenced by an area and the entity
            # has no explicitly set area
            or (
                not ent_entry.area_id
                and ent_entry.device_id in selected.referenced_devices
            )
            # The entity's device matches a targeted device
            or ent_entry.device_id in selector.device_ids
        ):
            selected.indirectly_referenced.add(ent_entry.entity_id)

    return selected


@bind_hass
async def async_extract_config_entry_ids(
    hass: HomeAssistant, service_call: ServiceCall, expand_group: bool = True
) -> set:
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
            _SERVICES_SCHEMA(load_yaml(str(integration.file_path / "services.yaml"))),
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


@bind_hass
async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Return descriptions (i.e. user documentation) for all service calls."""
    descriptions_cache: dict[
        tuple[str, str], dict[str, Any] | None
    ] = hass.data.setdefault(SERVICE_DESCRIPTION_CACHE, {})
    services = hass.services.async_services()

    # See if there are new services not seen before.
    # Any service that we saw before already has an entry in description_cache.
    missing = set()
    all_services = []
    for domain in services:
        for service_name in services[domain]:
            cache_key = (domain, service_name)
            all_services.append(cache_key)
            if cache_key not in descriptions_cache:
                missing.add(domain)

    # If we have a complete cache, check if it is still valid
    if all_cache := hass.data.get(ALL_SERVICE_DESCRIPTIONS_CACHE):
        previous_all_services, previous_descriptions_cache = all_cache
        # If the services are the same, we can return the cache
        if previous_all_services == all_services:
            return cast(dict[str, dict[str, Any]], previous_descriptions_cache)

    # Files we loaded for missing descriptions
    loaded: dict[str, JSON_TYPE] = {}

    if missing:
        ints_or_excs = await async_get_integrations(hass, missing)
        integrations: list[Integration] = []
        for domain, int_or_exc in ints_or_excs.items():
            if type(int_or_exc) is Integration:  # noqa: E721
                integrations.append(int_or_exc)
                continue
            if TYPE_CHECKING:
                assert isinstance(int_or_exc, Exception)
            _LOGGER.error("Failed to load integration: %s", domain, exc_info=int_or_exc)
        contents = await hass.async_add_executor_job(
            _load_services_files, hass, integrations
        )
        loaded = dict(zip(missing, contents))

    # Load translations for all service domains
    translations = await translation.async_get_translations(
        hass, "en", "services", list(services)
    )

    # Build response
    descriptions: dict[str, dict[str, Any]] = {}
    for domain, services_map in services.items():
        descriptions[domain] = {}
        domain_descriptions = descriptions[domain]

        for service_name in services_map:
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

            if (
                response := hass.services.supports_response(domain, service_name)
            ) != SupportsResponse.NONE:
                description["response"] = {
                    "optional": response == SupportsResponse.OPTIONAL,
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

    descriptions_cache: dict[
        tuple[str, str], dict[str, Any] | None
    ] = hass.data.setdefault(SERVICE_DESCRIPTION_CACHE, {})

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
    platforms: Iterable[EntityPlatform],
    entity_perms: None | (Callable[[str, str], bool]),
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
                for platform in platforms
                for entity in platform.entities.values()
                if entity_perms(entity.entity_id, POLICY_CONTROL)
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
        return [
            entity for platform in platforms for entity in platform.entities.values()
        ]

    # We have already validated they have permissions to control all_referenced
    # entities so we do not need to check again.
    assert all_referenced is not None
    if single_entity := len(all_referenced) == 1 and list(all_referenced)[0]:
        for platform in platforms:
            if (entity := platform.entities.get(single_entity)) is not None:
                return [entity]

    return [
        platform.entities[entity_id]
        for platform in platforms
        for entity_id in all_referenced.intersection(platform.entities)
    ]


@bind_hass
async def entity_service_call(
    hass: HomeAssistant,
    platforms: Iterable[EntityPlatform],
    func: str | Callable[..., Coroutine[Any, Any, ServiceResponse]],
    call: ServiceCall,
    required_features: Iterable[int] | None = None,
) -> EntityServiceResponse | None:
    """Handle an entity service call.

    Calls all platforms simultaneously.
    """
    entity_perms: None | (Callable[[str, str], bool]) = None
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
        platforms,
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
                raise HomeAssistantError(
                    f"Entity {entity.entity_id} does not support this service."
                )

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
    for entity, result in zip(entities, results):
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
        tasks.append(asyncio.create_task(entity.async_update_ha_state(True)))

    if tasks:
        done, pending = await asyncio.wait(tasks)
        assert not pending
        for future in done:
            future.result()  # pop exception if have

    return response_data if return_response and response_data else None


async def _handle_entity_call(
    hass: HomeAssistant,
    entity: Entity,
    func: str | Callable[..., Coroutine[Any, Any, ServiceResponse]],
    data: dict | ServiceCall,
    context: Context,
) -> ServiceResponse:
    """Handle calling service method."""
    entity.async_set_context(context)

    task: asyncio.Future[ServiceResponse] | None
    if isinstance(func, str):
        task = hass.async_run_job(
            partial(getattr(entity, func), **data)  # type: ignore[arg-type]
        )
    else:
        task = hass.async_run_job(func, entity, data)

    # Guard because callback functions do not return a task when passed to
    # async_run_job.
    result: ServiceResponse = None
    if task is not None:
        result = await task

    if asyncio.iscoroutine(result):
        _LOGGER.error(
            (
                "Service %s for %s incorrectly returns a coroutine object. Await result"
                " instead in service handler. Report bug to integration author"
            ),
            func,
            entity.entity_id,
        )
        result = await result

    return result


@bind_hass
@callback
def async_register_admin_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    service_func: Callable[[ServiceCall], Awaitable[None] | None],
    schema: vol.Schema = vol.Schema({}, extra=vol.PREVENT_EXTRA),
) -> None:
    """Register a service that requires admin access."""

    @wraps(service_func)
    async def admin_handler(call: ServiceCall) -> None:
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
            if not user.is_admin:
                raise Unauthorized(context=call.context)

        result = hass.async_run_job(service_func, call)
        if result is not None:
            await result

    hass.services.async_register(domain, service, admin_handler, schema)


@bind_hass
@callback
def verify_domain_control(
    hass: HomeAssistant, domain: str
) -> Callable[[Callable[[ServiceCall], Any]], Callable[[ServiceCall], Any]]:
    """Ensure permission to access any entity under domain in service call."""

    def decorator(
        service_handler: Callable[[ServiceCall], Any]
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


class ReloadServiceHelper:
    """Helper for reload services to minimize unnecessary reloads."""

    def __init__(self, service_func: Callable[[ServiceCall], Awaitable]) -> None:
        """Initialize ReloadServiceHelper."""
        self._service_func = service_func
        self._service_running = False
        self._service_condition = asyncio.Condition()

    async def execute_service(self, service_call: ServiceCall) -> None:
        """Execute the service.

        If a previous reload task if currently in progress, wait for it to finish first.
        Once the previous reload task has finished, one of the waiting tasks will be
        assigned to execute the reload, the others will wait for the reload to finish.
        """

        do_reload = False
        async with self._service_condition:
            if self._service_running:
                # A previous reload task is already in progress, wait for it to finish
                await self._service_condition.wait()

        async with self._service_condition:
            if not self._service_running:
                # This task will do the reload
                self._service_running = True
                do_reload = True
            else:
                # Another task will perform the reload, wait for it to finish
                await self._service_condition.wait()

        if do_reload:
            # Reload, then notify other tasks
            await self._service_func(service_call)
            async with self._service_condition:
                self._service_running = False
                self._service_condition.notify_all()
