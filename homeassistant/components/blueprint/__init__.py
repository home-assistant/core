"""The blueprint integration."""

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_SELECTOR
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.selector import selector as create_selector
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import CONF_USE_BLUEPRINT, DOMAIN  # noqa: F401
from .errors import (  # noqa: F401
    BlueprintException,
    BlueprintInUse,
    BlueprintWithNameException,
    FailedToLoad,
    InvalidBlueprint,
    InvalidBlueprintInputs,
    MissingInput,
)
from .models import Blueprint, BlueprintInputs, DomainBlueprints  # noqa: F401
from .schemas import (  # noqa: F401
    BLUEPRINT_INSTANCE_FIELDS,
    BLUEPRINT_SCHEMA,
    is_blueprint_instance_config,
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the blueprint integration."""
    websocket_api.async_setup(hass)
    return True


async def async_find_relevant_blueprints(
    hass: HomeAssistant, device_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Find all blueprints relevant to a specific device."""
    results = {}
    entities = [
        entry
        for entry in er.async_entries_for_device(er.async_get(hass), device_id)
        if not entry.entity_category
    ]

    async def all_blueprints_generator(hass: HomeAssistant):
        """Yield all blueprints from all domains."""
        blueprint_domains: dict[str, DomainBlueprints] = hass.data[DOMAIN]
        for blueprint_domain in blueprint_domains.values():
            blueprints = await blueprint_domain.async_get_blueprints()
            for blueprint in blueprints.values():
                yield blueprint

    async for blueprint in all_blueprints_generator(hass):
        blueprint_input_matches: dict[str, list[str]] = {}

        for info in blueprint.inputs.values():
            if (
                not info
                or not (selector_conf := info.get(CONF_SELECTOR))
                or "entity" not in selector_conf
            ):
                continue

            selector = create_selector(selector_conf)

            matched = []

            for entity in entities:
                try:
                    entity.entity_id, selector(entity.entity_id)
                except vol.Invalid:
                    continue

                matched.append(entity.entity_id)

            if matched:
                blueprint_input_matches[info[CONF_NAME]] = matched

        if not blueprint_input_matches:
            continue

        results.setdefault(blueprint.domain, []).append(
            {
                "blueprint": blueprint,
                "matched_input": blueprint_input_matches,
            }
        )

    return results
