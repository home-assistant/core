"""Test template trigger entity."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.trigger_template_entity import ManualTriggerEntity


async def test_template_entity_requires_hass_set(hass: HomeAssistant) -> None:
    """Test manual trigger template entity."""
    config = {
        "name": template.Template("test_entity", hass),
        "icon": template.Template(
            '{% if value=="on" %} mdi:on {% else %} mdi:off {% endif %}', hass
        ),
        "picture": template.Template(
            '{% if value=="on" %} /local/picture_on {% else %} /local/picture_off {% endif %}',
            hass,
        ),
    }

    entity = ManualTriggerEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", "on")
    await entity.async_added_to_hass()

    entity._process_manual_data("on")
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"

    hass.states.async_set("test.entity", "off")
    await entity.async_added_to_hass()
    entity._process_manual_data("off")
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"
