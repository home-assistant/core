"""Test template entity."""
import pytest

from homeassistant.components.template import template_entity
from homeassistant.helpers import template


async def test_template_entity_requires_hass_set():
    """Test template entity requires hass to be set before accepting templates."""
    entity = template_entity.TemplateEntity()

    with pytest.raises(AssertionError):
        entity.add_template_attribute("_hello", template.Template("Hello"))

    entity.hass = object()
    entity.add_template_attribute("_hello", template.Template("Hello", None))

    tpl_with_hass = template.Template("Hello", entity.hass)
    entity.add_template_attribute("_hello", tpl_with_hass)

    # Because hass is set in `add_template_attribute`, both templates match `tpl_with_hass`
    assert len(entity._template_attrs.get(tpl_with_hass, [])) == 2
