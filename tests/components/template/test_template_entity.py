"""Test template entity."""

import pytest

from homeassistant.components.template import template_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template


async def test_template_entity_requires_hass_set(hass: HomeAssistant) -> None:
    """Test template entity requires hass to be set before accepting templates."""
    entity = template_entity.TemplateEntity(hass, {}, "something_unique")

    with pytest.raises(ValueError, match="^template.hass cannot be None"):
        entity.add_template_attribute("_hello", template.Template("Hello", None))

    tpl_with_hass = template.Template("Hello", entity.hass)
    entity.add_template_attribute("_hello", tpl_with_hass)

    assert len(entity._template_attrs.get(tpl_with_hass, [])) == 1


async def test_default_entity_id(hass: HomeAssistant) -> None:
    """Test template entity creates suggested entity_id from the default_entity_id."""

    class TemplateTest(template_entity.TemplateEntity):
        _entity_id_format = "test.{}"

    entity = TemplateTest(hass, {"default_entity_id": "test.test"}, "a")
    assert entity.entity_id == "test.test"


async def test_bad_default_entity_id(hass: HomeAssistant) -> None:
    """Test template entity creates suggested entity_id from the default_entity_id."""

    class TemplateTest(template_entity.TemplateEntity):
        _entity_id_format = "test.{}"

    entity = TemplateTest(hass, {"default_entity_id": "bad.test"}, "a")
    assert entity.entity_id == "test.test"
