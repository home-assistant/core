"""Condition description helpers."""

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

from .models import CONDITIONS

_LOGGER = logging.getLogger(__name__)

CONDITION_DESCRIPTION_CACHE: HassKey[dict[str, dict[str, Any] | None]] = HassKey(
    "condition_description_cache"
)

# Basic schemas to sanity check the condition descriptions,
# full validation is done by hassfest.conditions
_FIELD_DESCRIPTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_SELECTOR): selector.validate_selector,
    },
    extra=probatio.ALLOW_EXTRA,
)

_CONDITION_DESCRIPTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional("target"): TargetSelector.CONFIG_SCHEMA,
        probatio.Optional("fields"): probatio.Schema({str: _FIELD_DESCRIPTION_SCHEMA}),
    },
    extra=probatio.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise probatio.Invalid("Key does not start with .")
    return key


_CONDITIONS_DESCRIPTION_SCHEMA = probatio.Schema(
    {
        probatio.Remove(probatio.All(str, starts_with_dot)): object,
        cv.underscore_slug: probatio.Any(None, _CONDITION_DESCRIPTION_SCHEMA),
    }
)


def _load_conditions_file(integration: Integration) -> dict[str, Any]:
    """Load conditions file for an integration."""
    try:
        return cast(
            dict[str, Any],
            _CONDITIONS_DESCRIPTION_SCHEMA(
                load_yaml_dict(str(integration.file_path / "conditions.yaml"))
            ),
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Unable to find conditions.yaml for the %s integration", integration.domain
        )
        return {}
    except (HomeAssistantError, probatio.Invalid) as ex:
        _LOGGER.warning(
            "Unable to parse conditions.yaml for the %s integration: %s",
            integration.domain,
            ex,
        )
        return {}


def _load_conditions_files(
    integrations: Iterable[Integration],
) -> dict[str, dict[str, Any]]:
    """Load condition files for multiple integrations."""
    return {
        integration.domain: {
            get_absolute_description_key(integration.domain, key): value
            for key, value in _load_conditions_file(integration).items()
        }
        for integration in integrations
    }


async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any] | None]:
    """Return descriptions (i.e. user documentation) for all conditions."""
    descriptions_cache = hass.data[CONDITION_DESCRIPTION_CACHE]

    conditions = hass.data[CONDITIONS]
    # See if there are new conditions not seen before.
    # Any condition that we saw before already has an entry in description_cache.
    all_conditions = set(conditions)
    previous_all_conditions = set(descriptions_cache)
    # If the conditions are the same, we can return the cache
    if previous_all_conditions == all_conditions:
        return descriptions_cache

    # Files we loaded for missing descriptions
    new_conditions_descriptions: dict[str, dict[str, Any]] = {}
    # We try to avoid making a copy in the event the cache is good,
    # but now we must make a copy in case new conditions get added
    # while we are loading the missing ones so we do not
    # add the new ones to the cache without their descriptions
    conditions = conditions.copy()

    if missing_conditions := all_conditions.difference(descriptions_cache):
        domains_with_missing_conditions = {
            conditions[missing_condition] for missing_condition in missing_conditions
        }
        ints_or_excs = await async_get_integrations(
            hass, domains_with_missing_conditions
        )
        integrations: list[Integration] = []
        for domain, int_or_exc in ints_or_excs.items():
            if type(int_or_exc) is Integration and int_or_exc.has_conditions:
                integrations.append(int_or_exc)
                continue
            if TYPE_CHECKING:
                assert isinstance(int_or_exc, Exception)
            _LOGGER.debug(
                "Failed to load conditions.yaml for integration: %s",
                domain,
                exc_info=int_or_exc,
            )

        if integrations:
            new_conditions_descriptions = await hass.async_add_executor_job(
                _load_conditions_files, integrations
            )

    # Make a copy of the old cache and add missing descriptions to it
    new_descriptions_cache = descriptions_cache.copy()
    for missing_condition in missing_conditions:
        domain = conditions[missing_condition]
        if (
            yaml_description := new_conditions_descriptions.get(domain, {}).get(
                missing_condition
            )
        ) is None:
            _LOGGER.debug(
                "No condition descriptions found for condition %s, skipping",
                missing_condition,
            )
            new_descriptions_cache[missing_condition] = None
            continue

        description = {"fields": yaml_description.get("fields", {})}
        if (target := yaml_description.get("target")) is not None:
            description["target"] = target

        new_descriptions_cache[missing_condition] = description

    hass.data[CONDITION_DESCRIPTION_CACHE] = new_descriptions_cache
    return new_descriptions_cache
