"""Test template entity."""
from datetime import date, datetime, timedelta

import pytest

from homeassistant.components.template import template_entity
from homeassistant.core import State
from homeassistant.helpers import template

from tests.common import mock_restore_cache_with_extra_data


async def test_template_entity_requires_hass_set(hass):
    """Test template entity requires hass to be set before accepting templates."""
    entity = template_entity.TemplateEntity(hass)

    with pytest.raises(AssertionError):
        entity.add_template_attribute("_hello", template.Template("Hello"))

    entity.hass = object()
    entity.add_template_attribute("_hello", template.Template("Hello", None))

    tpl_with_hass = template.Template("Hello", entity.hass)
    entity.add_template_attribute("_hello", tpl_with_hass)

    # Because hass is set in `add_template_attribute`, both templates match `tpl_with_hass`
    assert len(entity._template_attrs.get(tpl_with_hass, [])) == 2


async def test_template_entity_save_state(hass):
    """Test saving for a template entity."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.restore = True
    entity.hass = hass

    # Setup standard TemplateEntity templates
    _setup_attribute_templates(entity)
    setattr(entity, "_attr_available", "availability")
    setattr(entity, "_attr_icon", "icon")
    setattr(entity, "_attr_entity_picture", "entity picture")
    setattr(entity, "_attr_name", "friendly name")
    entity._attr_extra_state_attributes = {"attr": "attribute"}

    # Add additional class items to be stored for date, datetime, and timedelta
    setattr(entity, "_date", date(year=2022, month=3, day=22))
    setattr(
        entity,
        "_datetime",
        datetime(year=2022, month=3, day=22, hour=12, minute=00, second=00),
    )
    setattr(entity, "_timedelta", timedelta(days=1, seconds=5, milliseconds=0))

    # Add additional template attribute to be stored.
    entity.add_template_attribute("_hello", template.Template("{{ 'Hello' }}"))
    setattr(entity, "_hello", "Hello")

    # Add additional static attribute that is not to be stored.
    entity.add_template_attribute("_hellostatic", template.Template("Hello"))
    setattr(entity, "_hellostatic", "Hello")

    restored_extra_data = entity.extra_restore_state_data.as_dict()

    # Confirm standard TemplateEntity templates
    assert restored_extra_data["_attr_available"] == "availability"
    assert restored_extra_data["_attr_icon"] == "icon"
    assert restored_extra_data["_attr_entity_picture"] == "entity picture"
    assert restored_extra_data["_attr_name"] == "friendly name"

    # Confirm additional template attribute
    assert restored_extra_data["_hello"] == "Hello"

    # Confirm additional static template attribute is not saved
    with pytest.raises(KeyError):
        assert restored_extra_data["_hellostatic"]

    # Confirm additional class items for date, datetime, and timedelta
    assert restored_extra_data["_date"] == {
        "__type": "<class 'datetime.date'>",
        "isoformat": "2022-03-22",
    }
    assert restored_extra_data["_datetime"] == {
        "__type": "<class 'datetime.datetime'>",
        "isoformat": "2022-03-22T12:00:00",
    }
    assert restored_extra_data["_timedelta"] == {
        "__type": "<class 'datetime.timedelta'>",
        "repr": {"days": 1, "seconds": 5, "microseconds": 0},
    }


async def test_template_entity_restore_state(hass):
    """Test restoring for a template entity."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    _setup_attribute_templates(entity)

    entity.add_additional_data("_attr_state")
    entity._attr_extra_state_attributes = {"attr": None}

    setattr(entity, "_date", None)

    setattr(entity, "_datetime", None)

    setattr(entity, "_timedelta", None)

    fake_state = State("sensor.restore", "not used", {"attr": "attribute"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    "_attr_state": "restored",
                    "_date": {
                        "__type": "<class 'datetime.date'>",
                        "isoformat": "2022-03-22",
                    },
                    "_datetime": {
                        "__type": "<class 'datetime.datetime'>",
                        "isoformat": "2022-03-22T12:00:00",
                    },
                    "_timedelta": {
                        "__type": "<class 'datetime.timedelta'>",
                        "repr": {"days": 1, "seconds": 5, "microseconds": 0},
                    },
                },
            ),
        ),
    )

    await entity.restore_entity()

    assert entity.state == "restored"

    attributes = entity.extra_state_attributes
    assert attributes

    assert attributes["attr"]
    assert attributes["attr"] == "attribute"

    assert getattr(entity, "_date") == date(year=2022, month=3, day=22)
    assert getattr(entity, "_datetime") == datetime(
        year=2022, month=3, day=22, hour=12, minute=00, second=00
    )
    assert getattr(entity, "_timedelta") == timedelta(days=1, seconds=5, milliseconds=0)


def _setup_attribute_templates(entity):
    """Template Entity templates setup."""

    entity._availability_template = template.Template("{{ 'availability' }}")
    entity._icon_template = template.Template("{{ 'icon' }}")
    entity._entity_picture_template = template.Template("{{ 'picture' }}")
    entity._friendly_name_template = template.Template("{{ 'friendly name' }}")

    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}

    entity._add_all_template_attributes()

    entity.add_additional_data("_date")
    entity.add_additional_data("_datetime")
    entity.add_additional_data("_timedelta")
