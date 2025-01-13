"""Test template entity."""

import pytest

from homeassistant.components import sensor
from homeassistant.components.template import template_entity
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
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


@pytest.mark.parametrize(("count", "domain"), [(1, sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "availability_template": "{{ is_state('sensor.test_sensor', 'on') }}",
                        "icon_template": "{% if states.sensor.test_sensor.state == 'on' %}mdi:on{% else %}mdi:off{% endif %}",
                    }
                },
            },
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_unavailable_does_not_render_other_state_attributes(
    hass: HomeAssistant,
) -> None:
    """Test when entity goes unavailable, other state attributes are not rendered."""
    hass.states.async_set("sensor.test_sensor", STATE_OFF)

    # When template returns true..
    hass.states.async_set("sensor.test_sensor", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("sensor.test_template_sensor").state != STATE_UNAVAILABLE
    assert hass.states.get("sensor.test_template_sensor").attributes["icon"] == "mdi:on"

    # When Availability template returns false
    hass.states.async_set("sensor.test_sensor", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("sensor.test_template_sensor").state == STATE_UNAVAILABLE
    # Icon should be mdi:on as going unavailable does not render state attributes
    assert hass.states.get("sensor.test_template_sensor").attributes["icon"] == "mdi:on"
