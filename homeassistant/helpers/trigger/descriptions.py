"""Triggers description helpers."""

from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING, Any, cast

import probatio

from homeassistant.const import CONF_SELECTOR
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.automation import get_absolute_description_key
from homeassistant.helpers.selector import TargetSelector
from homeassistant.loader import Integration, async_get_integrations
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.yaml import load_yaml_dict

from .models import TRIGGER_CLASSES, TRIGGERS, has_dynamic_fields_schema

_LOGGER = logging.getLogger(__name__)

TRIGGER_DESCRIPTION_CACHE: HassKey[dict[str, dict[str, Any] | None]] = HassKey(
    "trigger_description_cache"
)

# Basic schemas to sanity check the trigger descriptions,
# full validation is done by hassfest.triggers
_FIELD_DESCRIPTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_SELECTOR): selector.validate_selector,
    },
    extra=probatio.ALLOW_EXTRA,
)

_FIELDS_DESCRIPTION_SCHEMA = probatio.Schema({str: _FIELD_DESCRIPTION_SCHEMA})

_TRIGGER_DESCRIPTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional("target"): TargetSelector.CONFIG_SCHEMA,
        probatio.Optional("fields"): _FIELDS_DESCRIPTION_SCHEMA,
    },
    extra=probatio.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise probatio.Invalid("Key does not start with .")
    return key


_TRIGGERS_DESCRIPTION_SCHEMA = probatio.Schema(
    {
        probatio.Remove(probatio.All(str, starts_with_dot)): object,
        cv.underscore_slug: probatio.Any(None, _TRIGGER_DESCRIPTION_SCHEMA),
    }
)


def _load_triggers_file(integration: Integration) -> dict[str, Any]:
    """Load triggers file for an integration."""
    try:
        return cast(
            dict[str, Any],
            _TRIGGERS_DESCRIPTION_SCHEMA(
                load_yaml_dict(str(integration.file_path / "triggers.yaml"))
            ),
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Unable to find triggers.yaml for the %s integration", integration.domain
        )
        return {}
    except (HomeAssistantError, probatio.Invalid) as ex:
        _LOGGER.warning(
            "Unable to parse triggers.yaml for the %s integration: %s",
            integration.domain,
            ex,
        )
        return {}


def _load_triggers_files(
    integrations: Iterable[Integration],
) -> dict[str, dict[str, Any]]:
    """Load trigger files for multiple integrations."""
    return {
        integration.domain: {
            get_absolute_description_key(integration.domain, key): value
            for key, value in _load_triggers_file(integration).items()
        }
        for integration in integrations
    }


async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any] | None]:
    """Return descriptions (i.e. user documentation) for all triggers."""
    descriptions_cache = hass.data[TRIGGER_DESCRIPTION_CACHE]

    triggers = hass.data[TRIGGERS]
    trigger_classes = hass.data[TRIGGER_CLASSES]
    # See if there are new triggers not seen before.
    # Any trigger that we saw before already has an entry in description_cache.
    all_triggers = set(triggers)
    previous_all_triggers = set(descriptions_cache)
    # If the triggers are the same, we can return the cache
    if previous_all_triggers == all_triggers:
        return descriptions_cache

    # Files we loaded for missing descriptions
    new_triggers_descriptions: dict[str, dict[str, Any]] = {}
    # We try to avoid making a copy in the event the cache is good,
    # but now we must make a copy in case new triggers get added
    # while we are loading the missing ones so we do not
    # add the new ones to the cache without their descriptions
    triggers = triggers.copy()

    if missing_triggers := all_triggers.difference(descriptions_cache):
        domains_with_missing_triggers = {
            triggers[missing_trigger] for missing_trigger in missing_triggers
        }
        ints_or_excs = await async_get_integrations(hass, domains_with_missing_triggers)
        integrations: list[Integration] = []
        for domain, int_or_exc in ints_or_excs.items():
            if type(int_or_exc) is Integration and int_or_exc.has_triggers:
                integrations.append(int_or_exc)
                continue
            if TYPE_CHECKING:
                assert isinstance(int_or_exc, Exception)
            _LOGGER.debug(
                "Failed to load triggers.yaml for integration: %s",
                domain,
                exc_info=int_or_exc,
            )

        if integrations:
            new_triggers_descriptions = await hass.async_add_executor_job(
                _load_triggers_files, integrations
            )

    # Make a copy of the old cache and add missing descriptions to it
    new_descriptions_cache = descriptions_cache.copy()
    for missing_trigger in missing_triggers:
        domain = triggers[missing_trigger]
        if (
            yaml_description := new_triggers_descriptions.get(domain, {}).get(
                missing_trigger
            )
        ) is None:
            _LOGGER.debug(
                "No trigger descriptions found for trigger %s, skipping",
                missing_trigger,
            )
            new_descriptions_cache[missing_trigger] = None
            continue

        description = {"fields": yaml_description.get("fields", {})}
        if (target := yaml_description.get("target")) is not None:
            description["target"] = target
        if (
            trigger_cls := trigger_classes.get(missing_trigger)
        ) is not None and has_dynamic_fields_schema(trigger_cls):
            description["has_dynamic_fields"] = True

        new_descriptions_cache[missing_trigger] = description
    hass.data[TRIGGER_DESCRIPTION_CACHE] = new_descriptions_cache
    return new_descriptions_cache


def _fields_from_schema(schema: probatio.Schema) -> dict[str, dict[str, Any]]:
    """Convert a fields schema to the triggers.yaml field format."""
    fields: dict[str, dict[str, Any]] = {}
    field_list = cast(
        list[dict[str, Any]],
        probatio.to_field_list(schema, custom_serializer=cv.custom_serializer),
    )
    for item in field_list:
        if "selector" not in item:
            raise probatio.Invalid(f"Field '{item['name']}' must use a selector")
        field: dict[str, Any] = {
            "required": item["required"],
            "selector": item["selector"],
        }
        if "default" in item:
            field["default"] = item["default"]
        fields[item["name"]] = field
    return fields


async def async_get_description(
    hass: HomeAssistant, trigger_key: str
) -> dict[str, Any] | None:
    """Return the description of a trigger with its dynamic fields merged in.

    Returns None if the trigger is not registered or has no description.
    The returned dict is a new object; the description cache is not modified.
    """
    descriptions = await async_get_all_descriptions(hass)
    if (description := descriptions.get(trigger_key)) is None:
        return None
    if not description.get("has_dynamic_fields"):
        return dict(description)

    trigger_cls = hass.data[TRIGGER_CLASSES][trigger_key]
    try:
        schema = await trigger_cls.async_get_fields_schema(hass)
    except Exception:
        _LOGGER.exception("Error getting dynamic fields for trigger %s", trigger_key)
        return dict(description)
    if schema is None:
        return dict(description)
    try:
        dynamic_fields = _FIELDS_DESCRIPTION_SCHEMA(_fields_from_schema(schema))
    except (probatio.Invalid, ValueError) as ex:
        # The serializer raises ValueError for unsupported schemas, e.g. nested sections
        _LOGGER.warning("Invalid dynamic fields for trigger %s: %s", trigger_key, ex)
        return dict(description)

    static_fields: dict[str, dict[str, Any]] = description["fields"]
    fields = dict(static_fields)
    for name, field in dynamic_fields.items():
        fields[name] = {**static_fields.get(name, {}), **field}
    return {**description, "fields": fields}
