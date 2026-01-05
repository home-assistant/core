"""Test abstract template entity."""

import pytest

from homeassistant.components.template import entity as abstract_entity
from homeassistant.core import HomeAssistant


async def test_template_entity_not_implemented(hass: HomeAssistant) -> None:
    """Test abstract template entity raises not implemented error."""

    with pytest.raises(TypeError):
        _ = abstract_entity.AbstractTemplateEntity(hass, {})
