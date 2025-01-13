"""Test template trigger entity."""

from typing import Any

import pytest

from homeassistant.const import CONF_ICON, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ManualTriggerEntity,
)


async def test_template_entity_requires_hass_set(hass: HomeAssistant) -> None:
    """Test manual trigger template entity."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(
            '{% if value=="on" %} mdi:on {% else %} mdi:off {% endif %}', hass
        ),
        CONF_PICTURE: template.Template(
            '{% if value=="on" %} /local/picture_on {% else %} /local/picture_off {% endif %}',
            hass,
        ),
    }

    entity = ManualTriggerEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(STATE_ON)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"

    hass.states.async_set("test.entity", STATE_OFF)
    await entity.async_added_to_hass()
    entity._process_manual_data(STATE_OFF)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"


async def test_trigger_template_availability(hass: HomeAssistant) -> None:
    """Test manual trigger template entity availability template."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(
            '{% if value=="on" %} mdi:on {% else %} mdi:off {% endif %}', hass
        ),
        CONF_PICTURE: template.Template(
            '{% if value=="on" %} /local/picture_on {% else %} /local/picture_off {% endif %}',
            hass,
        ),
        CONF_AVAILABILITY: template.Template('{{ has_value("test.entity") }}', hass),
    }

    entity = ManualTriggerEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(STATE_ON)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"
    assert entity.available is True

    hass.states.async_set("test.entity", STATE_OFF)
    await entity.async_added_to_hass()
    entity._process_manual_data(STATE_OFF)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"
    assert entity.available is True

    hass.states.async_set("test.entity", STATE_UNKNOWN)
    await entity.async_added_to_hass()
    entity._process_manual_data(STATE_UNKNOWN)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"
    assert entity.available is False


async def test_trigger_template_availability_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when availability render fails."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(
            '{% if value=="on" %} mdi:on {% else %} mdi:off {% endif %}', hass
        ),
        CONF_PICTURE: template.Template(
            '{% if value=="on" %} /local/picture_on {% else %} /local/picture_off {% endif %}',
            hass,
        ),
        CONF_AVAILABILITY: template.Template("{{ incorrect ", hass),
    }

    entity = ManualTriggerEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(STATE_ON)
    await hass.async_block_till_done()

    assert "Error rendering availability template for test.entity" in caplog.text


async def test_trigger_template_complex(hass: HomeAssistant) -> None:
    """Test manual trigger template entity complex template."""
    complex_template = """
    {% set d = {'test_key':'test_data'} %}
    {{ dict(d) }}

"""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(
            '{% if value=="on" %} mdi:on {% else %} mdi:off {% endif %}', hass
        ),
        CONF_PICTURE: template.Template(
            '{% if value=="on" %} /local/picture_on {% else %} /local/picture_off {% endif %}',
            hass,
        ),
        CONF_AVAILABILITY: template.Template('{{ has_value("test.entity") }}', hass),
        "other_key": template.Template(complex_template, hass),
    }

    class TestEntity(ManualTriggerEntity):
        """Test entity class."""

        extra_template_keys_complex = ("other_key",)

        @property
        def some_other_key(self) -> dict[str, Any] | None:
            """Return extra attributes."""
            return self._rendered.get("other_key")

    entity = TestEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(STATE_ON)
    await hass.async_block_till_done()

    assert entity.some_other_key == {"test_key": "test_data"}
