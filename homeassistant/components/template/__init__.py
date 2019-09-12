"""The template component."""

import logging

from homeassistant.const import MATCH_ALL
from itertools import chain


_LOGGER = logging.getLogger(__name__)


def initialise_templates(hass, templates, attribute_templates=dict()):
    """Initialise templates and attribute templates."""
    for template_name, template in chain(
        templates.items(), attribute_templates.items()
    ):
        if template is None:
            continue
        template.hass = hass


def extract_entities(
    device_name, device_type, manual_entity_ids, templates, attribute_templates=dict()
):
    """Extract entity ids from templates and attribute templates."""
    entity_ids = set()
    if manual_entity_ids is None:
        invalid_templates = []
        for template_name, template in chain(
            templates.items(), attribute_templates.items()
        ):
            if template is None:
                continue

            template_entity_ids = template.extract_entities()
            if template_entity_ids == MATCH_ALL:
                entity_ids = MATCH_ALL
                # Cut off _template from name
                invalid_templates.append(template_name.replace("_template", ""))
            elif entity_ids != MATCH_ALL:
                entity_ids |= set(template_entity_ids)

        if invalid_templates:
            _LOGGER.warning(
                "Template %s '%s' has no entity ids configured to track nor"
                " were we able to extract the entities to track from the %s "
                "template(s). This entity will only be able to be updated "
                "manually.",
                device_type,
                device_name,
                ", ".join(invalid_templates),
            )

    if manual_entity_ids is not None:
        entity_ids = manual_entity_ids
    elif entity_ids != MATCH_ALL:
        entity_ids = list(entity_ids)

    return entity_ids
