"""Test template trigger entity."""

from typing import Any

import pytest

from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.trigger_template_entity import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ManualTriggerEntity,
)

_ICON_TEMPLATE = 'mdi:o{{ "n" if value=="on" else "ff" }}'
_PICTURE_TEMPLATE = '/local/picture_o{{ "n" if value=="on" else "ff" }}'


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


@pytest.mark.parametrize("state_attribute", [CONF_STATE, CONF_VALUE_TEMPLATE])
async def test_trigger_template_availability(
    hass: HomeAssistant, state_attribute: str
) -> None:
    """Test manual trigger template entity availability template."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_AVAILABILITY: template.Template('{{ has_value("test.entity") }}', hass),
        CONF_UNIQUE_ID: "9961786c-f8c8-4ea0-ab1d-b9e922c39088",
        state_attribute: template.Template("{{ value=='on' }}", hass),
        CONF_ATTRIBUTES: {"extra": template.Template("{{ value=='on' }}", hass)},
    }

    class TestEntity(ManualTriggerEntity):
        """Test entity class."""

        extra_template_keys = (state_attribute,)

        @property
        def state(self) -> bool | None:
            """Return extra attributes."""
            return self._rendered.get(state_attribute)

    entity = TestEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(STATE_ON)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"
    assert entity.unique_id == "9961786c-f8c8-4ea0-ab1d-b9e922c39088"
    assert entity.state == "True"
    assert entity.extra_state_attributes == {"extra": True}
    assert entity.available is True

    hass.states.async_set("test.entity", STATE_OFF)
    await entity.async_added_to_hass()
    entity._process_manual_data(STATE_OFF)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"
    assert entity.unique_id == "9961786c-f8c8-4ea0-ab1d-b9e922c39088"
    assert entity.state == "False"
    assert entity.extra_state_attributes == {"extra": False}
    assert entity.available is True

    hass.states.async_set("test.entity", STATE_UNKNOWN)
    await entity.async_added_to_hass()
    entity._process_manual_data(STATE_UNKNOWN)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon is None
    assert entity.entity_picture is None
    assert entity.unique_id == "9961786c-f8c8-4ea0-ab1d-b9e922c39088"
    assert entity.state is None
    assert entity.extra_state_attributes is None
    assert entity.available is False


@pytest.mark.parametrize("state_attribute", [CONF_STATE, CONF_VALUE_TEMPLATE])
async def test_template_render_with_availability_syntax_error(
    hass: HomeAssistant, state_attribute: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when availability render fails."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        state_attribute: template.Template("{{ value=='on' }}", hass),
        CONF_AVAILABILITY: template.Template("{{ incorrect ", hass),
    }

    class TestEntity(ManualTriggerEntity):
        """Test entity class."""

        extra_template_keys = (state_attribute,)

        @property
        def state(self) -> bool | None:
            """Return extra attributes."""
            return self._rendered.get(state_attribute)

    entity = TestEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(STATE_ON)
    await hass.async_block_till_done()

    assert "Error rendering availability template for test.entity" in caplog.text

    assert entity.state == "True"


@pytest.mark.parametrize("state_attribute", [CONF_STATE, CONF_VALUE_TEMPLATE])
async def test_template_state_syntax_error(
    hass: HomeAssistant, state_attribute: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when state render fails."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        state_attribute: template.Template("{{ incorrect ", hass),
    }

    class TestEntity(ManualTriggerEntity):
        """Test entity class."""

        extra_template_keys = (state_attribute,)

        @property
        def state(self) -> bool | None:
            """Return extra attributes."""
            return self._rendered.get(state_attribute)

    entity = TestEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(STATE_ON)
    await hass.async_block_till_done()

    assert f"Error rendering {state_attribute} template for test.entity" in caplog.text

    assert entity.state is None


async def test_attribute_order(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when availability render fails."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ATTRIBUTES: {
            "beer": template.Template("{{ value }}", hass),
            "no_beer": template.Template("{{ sad - 1 }}", hass),
            "more_beer": template.Template("{{ beer + 1 }}", hass),
        },
    }

    entity = ManualTriggerEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", STATE_ON)
    await entity.async_added_to_hass()

    entity._process_manual_data(1)
    await hass.async_block_till_done()

    assert entity.extra_state_attributes == {"beer": 1, "more_beer": 2}

    assert (
        "Error rendering attributes.no_beer template for test.entity: UndefinedError: 'sad' is undefined"
        in caplog.text
    )


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
