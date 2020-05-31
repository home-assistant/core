"""Common template functions."""

from itertools import chain
import logging
from typing import List

from homeassistant.const import MATCH_ALL
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.collection import (
    CHANGE_ADDED,
    CHANGE_REMOVED,
    CHANGE_UPDATED,
    ObservableCollection,
)
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

TEMPLATE_ENTITIES: List[str] = []


@callback
def attach_template_listener(
    hass: HomeAssistantType,
    domain: str,
    platform: str,
    collection: ObservableCollection,
) -> None:
    """Attach a lister to monitor for template entities added or removed."""

    async def _collection_changed(change_type: str, item_id: str, config: dict) -> None:
        """Handle a collection change."""
        if change_type == CHANGE_UPDATED:
            return

        ent_reg = await entity_registry.async_get_registry(hass)
        entity_id = ent_reg.async_get_entity_id(domain, platform, item_id)

        if change_type == CHANGE_ADDED:
            TEMPLATE_ENTITIES.append(entity_id)
            return

        if change_type == CHANGE_REMOVED:
            TEMPLATE_ENTITIES.pop(entity_id)
            return

    collection.async_add_listener(_collection_changed)


def initialise_templates(hass, templates, attribute_templates=None):
    """Initialise templates and attribute templates."""
    if attribute_templates is None:
        attribute_templates = {}
    for template in chain(templates.values(), attribute_templates.values()):
        if template is None:
            continue
        template.hass = hass


def extract_entities(
    device_name, device_type, manual_entity_ids, templates, attribute_templates=None
):
    """Extract entity ids from templates and attribute templates."""
    if attribute_templates is None:
        attribute_templates = {}
    entity_ids = set()
    if manual_entity_ids is None:
        invalid_templates = []
        for template_name, template in chain(
            templates.items(), attribute_templates.items()
        ):
            if template is None:
                continue

            template_entity_ids = template.extract_entities()

            if template_entity_ids != MATCH_ALL:
                entity_ids |= set(template_entity_ids)
            else:
                invalid_templates.append(template_name.replace("_template", ""))

        if invalid_templates:
            entity_ids = MATCH_ALL
            _LOGGER.warning(
                "Template %s '%s' has no entity ids configured to track nor"
                " were we able to extract the entities to track from the %s "
                "template(s). This entity will only be able to be updated "
                "manually.",
                device_type,
                device_name,
                ", ".join(invalid_templates),
            )
        else:
            entity_ids = list(entity_ids)
    else:
        entity_ids = manual_entity_ids

    return entity_ids
