"""The template component."""

from itertools import chain
import logging

from homeassistant.const import MATCH_ALL

_LOGGER = logging.getLogger(__name__)


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
                "manually",
                device_type,
                device_name,
                ", ".join(invalid_templates),
            )
        else:
            entity_ids = list(entity_ids)
    else:
        entity_ids = manual_entity_ids

    return entity_ids
