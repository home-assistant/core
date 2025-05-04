"""Test template trigger entity."""

from typing import Any

import pytest

from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
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
    ValueTemplate,
)

_ICON_TEMPLATE = 'mdi:o{{ "n" if value=="on" else "ff" }}'
_PICTURE_TEMPLATE = '/local/picture_o{{ "n" if value=="on" else "ff" }}'


@pytest.mark.parametrize(
    ("value", "test_template", "error_value", "expected", "error"),
    [
        (1, "{{ value == 1 }}", None, "True", None),
        (1, "1", None, "1", None),
        (
            1,
            "{{ x - 4 }}",
            None,
            None,
            "",
        ),
        (
            1,
            "{{ x - 4 }}",
            template._SENTINEL,
            template._SENTINEL,
            "Error parsing value for test.entity: 'x' is undefined (value: 1, template: {{ x - 4 }})",
        ),
    ],
)
async def test_value_template_object(
    hass: HomeAssistant,
    value: Any,
    test_template: str,
    error_value: Any,
    expected: Any,
    error: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test ValueTemplate object."""
    entity = ManualTriggerEntity(
        hass,
        {
            CONF_NAME: template.Template("test_entity", hass),
        },
    )
    entity.entity_id = "test.entity"

    value_template = ValueTemplate.from_template(template.Template(test_template, hass))

    variables = entity._template_variables_with_value(value)
    result = value_template.async_render_as_value_template(
        entity.entity_id, variables, error_value
    )

    assert result == expected

    if error is not None:
        assert error in caplog.text


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

    variables = entity._template_variables_with_value(STATE_ON)
    entity._process_manual_data(variables)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"

    hass.states.async_set("test.entity", STATE_OFF)
    await entity.async_added_to_hass()

    variables = entity._template_variables_with_value(STATE_OFF)
    entity._process_manual_data(variables)
    await hass.async_block_till_done()

    assert entity.name == "test_entity"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"


@pytest.mark.parametrize(
    ("test_template", "test_entity_state", "expected"),
    [
        ('{{ has_value("test.entity") }}', STATE_ON, True),
        ('{{ has_value("test.entity") }}', STATE_OFF, True),
        ('{{ has_value("test.entity") }}', STATE_UNKNOWN, False),
        ('{{ "a" if has_value("test.entity") else "b" }}', STATE_ON, False),
        ('{{ "something_not_boolean" }}', STATE_OFF, False),
        ("{{ 1 }}", STATE_OFF, True),
        ("{{ 0 }}", STATE_OFF, False),
    ],
)
async def test_trigger_template_availability(
    hass: HomeAssistant,
    test_template: str,
    test_entity_state: str,
    expected: bool,
) -> None:
    """Test manual trigger template entity availability template."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_AVAILABILITY: template.Template(test_template, hass),
        CONF_UNIQUE_ID: "9961786c-f8c8-4ea0-ab1d-b9e922c39088",
    }

    entity = ManualTriggerEntity(hass, config)
    entity.entity_id = "test.entity"
    hass.states.async_set("test.entity", test_entity_state)
    await entity.async_added_to_hass()

    variables = entity._template_variables()
    assert entity._render_availability_template(variables) is expected
    await hass.async_block_till_done()

    assert entity.unique_id == "9961786c-f8c8-4ea0-ab1d-b9e922c39088"
    assert entity.available is expected


async def test_trigger_no_availability_template(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when availability template isn't used."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_STATE: template.Template("{{ value == 'on' }}", hass),
    }

    class TestEntity(ManualTriggerEntity):
        """Test entity class."""

        extra_template_keys = (CONF_STATE,)

        @property
        def state(self) -> bool | None:
            """Return extra attributes."""
            return self._rendered.get(CONF_STATE)

    entity = TestEntity(hass, config)
    entity.entity_id = "test.entity"
    variables = entity._template_variables_with_value(STATE_ON)
    assert entity._render_availability_template(variables) is True
    assert entity.available is True
    entity._process_manual_data(variables)
    await hass.async_block_till_done()

    assert entity.state == "True"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"

    variables = entity._template_variables_with_value(STATE_OFF)
    assert entity._render_availability_template(variables) is True
    assert entity.available is True
    entity._process_manual_data(variables)
    await hass.async_block_till_done()

    assert entity.state == "False"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"


async def test_trigger_template_availability_with_syntax_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when availability render fails."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_AVAILABILITY: template.Template("{{ incorrect ", hass),
    }

    entity = ManualTriggerEntity(hass, config)
    entity.entity_id = "test.entity"

    variables = entity._template_variables()
    entity._render_availability_template(variables)
    assert entity.available is True

    assert "Error rendering availability template for test.entity" in caplog.text


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

    variables = entity._template_variables_with_value(1)
    entity._process_manual_data(variables)
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

    variables = entity._template_variables_with_value(STATE_ON)
    entity._process_manual_data(variables)
    await hass.async_block_till_done()

    assert entity.some_other_key == {"test_key": "test_data"}
