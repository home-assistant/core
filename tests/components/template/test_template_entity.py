"""Test template entity."""

import pytest

from homeassistant.components.template import template_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, template
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component


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


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({}, id="state"),
        pytest.param(
            {"triggers": {"trigger": "event", "event_type": "go"}}, id="trigger"
        ),
    ],
)
async def test_this_variable_after_entity_id_change(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, config: ConfigType
) -> None:
    """Test the this variable refers to the entity after its entity_id changed."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": {
                **config,
                "sensor": {
                    "unique_id": "test",
                    "name": "test",
                    "state": "{{ this.entity_id }}",
                    "attributes": {"me": "{{ this.entity_id }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.bus.async_fire("go")
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    assert state.state == "sensor.test"
    assert state.attributes["me"] == "sensor.test"

    entity_registry.async_update_entity("sensor.test", new_entity_id="sensor.renamed")
    await hass.async_block_till_done()
    hass.bus.async_fire("go")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test") is None
    state = hass.states.get("sensor.renamed")
    assert state.state == "sensor.renamed"
    assert state.attributes["me"] == "sensor.renamed"


async def test_this_state_after_entity_id_change(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template keeping its last value via this.state survives a rename."""
    hass.states.async_set("sensor.source", "5")
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": {
                "sensor": {
                    "unique_id": "test",
                    "name": "test",
                    "state": (
                        "{{ states('sensor.source') "
                        "if states('sensor.source') != 'off' else this.state }}"
                    ),
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("sensor.source", "off")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test").state == "5"

    entity_registry.async_update_entity("sensor.test", new_entity_id="sensor.renamed")
    await hass.async_block_till_done()

    # The templates are re-rendered after the state is written under the new id
    assert hass.states.get("sensor.renamed").state == "5"
    hass.states.async_set("sensor.source", "7")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.renamed").state == "7"
