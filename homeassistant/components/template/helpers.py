"""Helpers for template integration."""

from collections.abc import Callable
import itertools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import blueprint
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
    async_get_platforms,
)
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ADVANCED_OPTIONS,
    CONF_ATTRIBUTE_TEMPLATES,
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_OBJECT_ID,
    CONF_PICTURE,
    DATA_HASS_COORDINATORS,
    DATA_PLATFORMS,
    DOMAIN,
)
from .entity import AbstractTemplateEntity
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

DATA_BLUEPRINTS = "template_blueprints"

LEGACY_FIELDS = {
    CONF_ICON_TEMPLATE: CONF_ICON,
    CONF_ENTITY_PICTURE_TEMPLATE: CONF_PICTURE,
    CONF_AVAILABILITY_TEMPLATE: CONF_AVAILABILITY,
    CONF_ATTRIBUTE_TEMPLATES: CONF_ATTRIBUTES,
    CONF_FRIENDLY_NAME: CONF_NAME,
}

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


def rewrite_legacy_to_modern_config(
    hass: HomeAssistant,
    entity_cfg: dict[str, Any],
    extra_legacy_fields: dict[str, str],
) -> dict[str, Any]:
    """Rewrite legacy config."""
    entity_cfg = {**entity_cfg}

    for from_key, to_key in itertools.chain(
        LEGACY_FIELDS.items(), extra_legacy_fields.items()
    ):
        if from_key not in entity_cfg or to_key in entity_cfg:
            continue

        val = entity_cfg.pop(from_key)
        if isinstance(val, str):
            val = template.Template(val, hass)
        entity_cfg[to_key] = val

    if CONF_NAME in entity_cfg and isinstance(entity_cfg[CONF_NAME], str):
        entity_cfg[CONF_NAME] = template.Template(entity_cfg[CONF_NAME], hass)

    return entity_cfg


def rewrite_legacy_to_modern_configs(
    hass: HomeAssistant,
    entity_cfg: dict[str, dict],
    extra_legacy_fields: dict[str, str],
) -> list[dict]:
    """Rewrite legacy configuration definitions to modern ones."""
    entities = []
    for object_id, entity_conf in entity_cfg.items():
        entity_conf = {**entity_conf, CONF_OBJECT_ID: object_id}

        entity_conf = rewrite_legacy_to_modern_config(
            hass, entity_conf, extra_legacy_fields
        )

        if CONF_NAME not in entity_conf:
            entity_conf[CONF_NAME] = template.Template(object_id, hass)

        entities.append(entity_conf)

    return entities


async def async_setup_template_platform(
    hass: HomeAssistant,
    domain: str,
    config: ConfigType,
    state_entity_cls: type[TemplateEntity],
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
    legacy_fields: dict[str, str] | None = None,
    legacy_key: str | None = None,
) -> None:
    """Set up the Template platform."""
    if discovery_info is None:
        # Legacy Configuration
        if legacy_fields is not None:
            if legacy_key:
                definitions = rewrite_legacy_to_modern_configs(
                    hass, config[legacy_key], legacy_fields
                )
            else:
                definitions = [
                    rewrite_legacy_to_modern_config(hass, config, legacy_fields)
                ]
            async_add_entities(
                [
                    state_entity_cls(hass, definition, definition.get(CONF_UNIQUE_ID))
                    for definition in definitions
                ]
            )

        else:
            _LOGGER.warning(
                "Template %s entities can only be configured under template:", domain
            )


async def async_setup_template_entry(
    hass: HomeAssistant,
    domain: str,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    state_entity_cls: type[TemplateEntity],
    trigger_entity_cls: type[TriggerEntity] | None,
    config_entry_schema: vol.Schema | vol.All,
    replace_value_template: bool = False,
) -> None:
    """Setup the Template from a config entry."""

    if config_entry.source == SOURCE_IMPORT:
        # Entities from modern and trigger yaml configurations.
        if (platforms := hass.data[DATA_PLATFORMS]) and (
            definitions := platforms.get(domain)
        ):
            entities: list[TemplateEntity | TriggerEntity] = []
            for definition in definitions:
                # Trigger based configuration
                if (
                    (coordinator_id := definition.get("coordinator"))
                    and trigger_entity_cls
                    and (coordinators := hass.data[DATA_HASS_COORDINATORS])
                    and (coordinator := coordinators.get(coordinator_id))
                ):
                    entities.append(
                        trigger_entity_cls(
                            hass,
                            coordinator,
                            definition["config"],
                        )
                    )

                # Modern state based configuration
                elif coordinator_id is None:
                    entity_config: ConfigType = definition["config"]
                    unique_id = entity_config.get(CONF_UNIQUE_ID)
                    if unique_id and (
                        unique_id_prefix := definition.get(CONF_UNIQUE_ID)
                    ):
                        unique_id = f"{unique_id_prefix}-{unique_id}"
                    entities.append(state_entity_cls(hass, entity_config, unique_id))

            if entities:
                async_add_entities(entities)

    else:
        options = dict(config_entry.options)
        options.pop("template_type")

        if advanced_options := options.pop(CONF_ADVANCED_OPTIONS, None):
            options = {**options, **advanced_options}

        if replace_value_template and CONF_VALUE_TEMPLATE in options:
            options[CONF_STATE] = options.pop(CONF_VALUE_TEMPLATE)

        validated_config = config_entry_schema(options)

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
