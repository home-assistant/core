"""Test template entity."""

import pytest

from homeassistant.components.template import template_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template


async def test_template_entity_requires_hass_set(hass: HomeAssistant) -> None:
    """Test template entity requires hass to be set before accepting templates."""
    entity = template_entity.TemplateEntity(hass)

    with pytest.raises(ValueError, match="^hass cannot be None"):
        entity.add_template_attribute("_hello", template.Template("Hello"))

    entity.hass = object()
    with pytest.raises(ValueError, match="^template.hass cannot be None"):
        entity.add_template_attribute("_hello", template.Template("Hello", None))

    tpl_with_hass = template.Template("Hello", entity.hass)
    entity.add_template_attribute("_hello", tpl_with_hass)

    assert len(entity._template_attrs.get(tpl_with_hass, [])) == 1
