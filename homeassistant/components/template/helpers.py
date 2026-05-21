"""Helpers for template integration."""

from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import blueprint
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers import template
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
    async_create_platform_config_not_supported_issue,
    async_get_platforms,
)
from homeassistant.helpers.script import async_validate_actions_config
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import CONF_ADVANCED_OPTIONS, CONF_DEFAULT_ENTITY_ID, DOMAIN
from .entity import AbstractTemplateEntity
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

DATA_BLUEPRINTS = "template_blueprints"

_LOGGER = logging.getLogger(__name__)

type CreateTemplateEntitiesCallback = Callable[
    [type[TemplateEntity], AddEntitiesCallback, HomeAssistant, list[dict], str | None],
    None,
]


@callback
def templates_with_blueprint(hass: HomeAssistant, blueprint_path: str) -> list[str]:
    """Return all template entity ids that reference the blueprint."""
    return [
        entity_id
        for platform in async_get_platforms(hass, DOMAIN)
        for entity_id, template_entity in platform.entities.items()
        if isinstance(template_entity, AbstractTemplateEntity)
        and template_entity.referenced_blueprint == blueprint_path
    ]


@callback
def blueprint_in_template(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the blueprint the template entity is based on or None."""
    for platform in async_get_platforms(hass, DOMAIN):
        if isinstance(
            (template_entity := platform.entities.get(entity_id)),
            AbstractTemplateEntity,
        ):
            return template_entity.referenced_blueprint
    return None


def _blueprint_in_use(hass: HomeAssistant, blueprint_path: str) -> bool:
    """Return True if any template references the blueprint."""
    return len(templates_with_blueprint(hass, blueprint_path)) > 0


async def _reload_blueprint_templates(hass: HomeAssistant, blueprint_path: str) -> None:
    """Reload all templates that rely on a specific blueprint."""
    await hass.services.async_call(DOMAIN, SERVICE_RELOAD)


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> blueprint.DomainBlueprints:
    """Get template blueprints."""
    from .config import TEMPLATE_BLUEPRINT_SCHEMA  # noqa: PLC0415

    return blueprint.DomainBlueprints(
        hass,
        DOMAIN,
        _LOGGER,
        _blueprint_in_use,
        _reload_blueprint_templates,
        TEMPLATE_BLUEPRINT_SCHEMA,
    )


@callback
def async_create_template_tracking_entities(
    entity_cls: type[Entity],
    async_add_entities: AddEntitiesCallback,
    hass: HomeAssistant,
    definitions: list[dict],
    unique_id_prefix: str | None,
) -> None:
    """Create the template tracking entities."""
    entities: list[Entity] = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(entity_cls(hass, definition, unique_id))  # type: ignore[call-arg]
    async_add_entities(entities)


def _get_config_breadcrumbs(config: ConfigType) -> str:
    """Try to coerce entity information from the config."""
    breadcrumb = "Template Entity"
    # Default entity id should be in most legacy configuration because
    # it's created from the legacy slug. Vacuum and Lock do not have a
    # slug, therefore we need to use the name or unique_id.
    if (default_entity_id := config.get(CONF_DEFAULT_ENTITY_ID)) is not None:
        breadcrumb = default_entity_id.split(".")[-1]
    elif (unique_id := config.get(CONF_UNIQUE_ID)) is not None:
        breadcrumb = f"unique_id: {unique_id}"
    elif (name := config.get(CONF_NAME)) and isinstance(name, template.Template):
        breadcrumb = name.template
    return breadcrumb


async def validate_template_scripts(
    hass: HomeAssistant,
    config: ConfigType,
    script_options: tuple[str, ...] | None = None,
) -> None:
    """Validate template scripts."""
    if not script_options:
        return

    def _humanize(err: Exception, data: Any) -> str:
        """Humanize vol.Invalid, stringify other exceptions."""
        if isinstance(err, vol.Invalid):
            return humanize_error(data, err)
        return str(err)

    breadcrumb: str | None = None
    for script_option in script_options:
        if (script_config := config.pop(script_option, None)) is not None:
            try:
                config[script_option] = await async_validate_actions_config(
                    hass, script_config
                )
            except (vol.Invalid, HomeAssistantError) as err:
                if not breadcrumb:
                    breadcrumb = _get_config_breadcrumbs(config)
                _LOGGER.error(
                    "The '%s' actions for %s failed to setup: %s",
                    script_option,
                    breadcrumb,
                    _humanize(err, script_config),
                )


def async_create_platform_template_not_supported_issue(
    hass: HomeAssistant, domain: str
):
    """Create a platform: template not supported issue."""
    learn_more_url = (
        "https://www.home-assistant.io/integrations/template/"
        f"#{slugify(domain, separator='-')}"
    )
    async_create_platform_config_not_supported_issue(
        hass,
        DOMAIN,
        domain,
        yaml_config_under_integration_supported=True,
        learn_more_url=learn_more_url,
        logger=_LOGGER,
    )


async def async_setup_template_platform(
    hass: HomeAssistant,
    domain: str,
    config: ConfigType,
    state_entity_cls: type[TemplateEntity],
    trigger_entity_cls: type[TriggerEntity] | None,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
    script_options: tuple[str, ...] | None = None,
) -> None:
    """Set up the Template platform."""
    if discovery_info is None:
        # Legacy Configuration
        async_create_platform_template_not_supported_issue(hass, domain)
        return

    # Trigger Configuration
    if "coordinator" in discovery_info:
        if trigger_entity_cls:
            entities = []
            for entity_config in discovery_info["entities"]:
                await validate_template_scripts(hass, entity_config, script_options)
                entities.append(
                    trigger_entity_cls(
                        hass, discovery_info["coordinator"], entity_config
                    )
                )
            async_add_entities(entities)
        else:
            raise PlatformNotReady(
                f"The template {domain} platform doesn't support trigger entities"
            )
        return

    # Modern Configuration
    for entity_config in discovery_info["entities"]:
        await validate_template_scripts(hass, entity_config, script_options)

    async_create_template_tracking_entities(
        state_entity_cls,
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
    )


async def async_setup_template_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    state_entity_cls: type[TemplateEntity],
    config_schema: vol.Schema | vol.All,
    replace_value_template: bool = False,
    script_options: tuple[str, ...] | None = None,
) -> None:
    """Setup the Template from a config entry."""
    options = dict(config_entry.options)
    options.pop("template_type")

    if advanced_options := options.pop(CONF_ADVANCED_OPTIONS, None):
        options = {**options, **advanced_options}

    if replace_value_template and CONF_VALUE_TEMPLATE in options:
        options[CONF_STATE] = options.pop(CONF_VALUE_TEMPLATE)

    validated_config = config_schema(options)
    await validate_template_scripts(hass, validated_config, script_options)

    async_add_entities(
        [state_entity_cls(hass, validated_config, config_entry.entry_id)]
    )


def async_setup_template_preview[T: TemplateEntity](
    hass: HomeAssistant,
    name: str,
    config: ConfigType,
    state_entity_cls: type[T],
    schema: vol.Schema | vol.All,
    replace_value_template: bool = False,
) -> T:
    """Setup the Template preview."""
    if replace_value_template and CONF_VALUE_TEMPLATE in config:
        config[CONF_STATE] = config.pop(CONF_VALUE_TEMPLATE)

    validated_config = schema(config | {CONF_NAME: name})
    return state_entity_cls(hass, validated_config, None)
