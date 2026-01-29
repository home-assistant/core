"""Test trigger template entity."""

import pytest

from homeassistant.components.template import DOMAIN, trigger_entity
from homeassistant.components.template.coordinator import TriggerUpdateCoordinator
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_STATE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import template
from homeassistant.helpers.trigger_template_entity import CONF_PICTURE
from homeassistant.setup import async_setup_component

from .conftest import async_trigger

from tests.common import assert_setup_component

_ICON_TEMPLATE = 'mdi:o{{ "n" if value=="on" else "ff" }}'
_PICTURE_TEMPLATE = '/local/picture_o{{ "n" if value=="on" else "ff" }}'


class TestEntity(trigger_entity.TriggerEntity):
    """Test entity class."""

    __test__ = False
    _entity_id_format = "test.{}"
    extra_template_keys = (CONF_STATE,)

    @property
    def state(self) -> bool | None:
        """Return extra attributes."""
        return self._rendered.get(CONF_STATE)


async def test_reference_blueprints_is_none(hass: HomeAssistant) -> None:
    """Test template entity requires hass to be set before accepting templates."""
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = trigger_entity.TriggerEntity(hass, coordinator, {})

    assert entity.referenced_blueprint is None


async def test_template_state(hass: HomeAssistant) -> None:
    """Test manual trigger template entity with a state."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_STATE: template.Template("{{ value == 'on' }}", hass),
    }

    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"

    coordinator._execute_update({"value": STATE_ON})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.state == "True"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"

    coordinator._execute_update({"value": STATE_OFF})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.state == "False"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"


async def test_bad_template_state(hass: HomeAssistant) -> None:
    """Test manual trigger template entity with a state."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_STATE: template.Template("{{ x - 1 }}", hass),
    }
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"

    coordinator._execute_update({"x": 1})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.available is True
    assert entity.state == "0"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"

    coordinator._execute_update({"value": STATE_OFF})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.available is False
    assert entity.state is None
    assert entity.icon is None
    assert entity.entity_picture is None


async def test_template_state_syntax_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when state render fails."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_STATE: template.Template("{{ incorrect ", hass),
    }

    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"

    coordinator._execute_update({"value": STATE_ON})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert f"Error rendering {CONF_STATE} template for test.entity" in caplog.text

    assert entity.state is None
    assert entity.icon is None
    assert entity.entity_picture is None


async def test_script_variables_from_coordinator(
    hass: HomeAssistant, calls: list[ServiceCall], caplog: pytest.LogCaptureFixture
) -> None:
    """Test script variables."""
    await async_trigger(hass, "sensor.start", "1")
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "variables": {"a": "{{ states('sensor.start') }}", "c": 0},
                    "triggers": {
                        "trigger": "state",
                        "entity_id": ["sensor.trigger"],
                    },
                    "actions": [
                        {
                            "action": "test.automation",
                            "data": {
                                "a": "{{ a }}",
                                "b": "{{ b }}",
                                "c": "{{ c }}",
                            },
                        }
                    ],
                    "sensor": {
                        "name": "test",
                        "state": "{{ 'on' }}",
                        "variables": {"b": "{{ a + 1 }}", "c": 1},
                        "attributes": {
                            "a": "{{ a }}",
                            "b": "{{ b }}",
                            "c": "{{ c }}",
                        },
                    },
                },
            },
        )
    await async_trigger(hass, "sensor.trigger", "anything")

    assert len(calls) == 1
    assert calls[0].data["a"] == 1
    assert calls[0].data["c"] == 0
    assert "'b' is undefined when rendering '{{ b }}'" in caplog.text

    state = hass.states.get("sensor.test")
    assert state
    assert state.state == "on"
    assert state.attributes["a"] == 1
    assert state.attributes["b"] == 2
    assert state.attributes["c"] == 1


async def test_default_entity_id(hass: HomeAssistant) -> None:
    """Test template entity creates suggested entity_id from the default_entity_id."""
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, {"default_entity_id": "test.test"})
    assert entity.entity_id == "test.test"


async def test_bad_default_entity_id(hass: HomeAssistant) -> None:
    """Test template entity creates suggested entity_id from the default_entity_id."""
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, {"default_entity_id": "bad.test"})
    assert entity.entity_id == "test.test"


async def test_multiple_template_validators(hass: HomeAssistant) -> None:
    """Tests multiple templates execute validators."""
    await async_trigger(hass, "sensor.state", "opening")
    await async_trigger(hass, "sensor.position", "50")
    await async_trigger(hass, "sensor.tilt", "49")
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "triggers": {
                        "trigger": "state",
                        "entity_id": ["sensor.trigger"],
                    },
                    "cover": {
                        "name": "test",
                        "state": "{{ states('sensor.state') }}",
                        "position": "{{ states('sensor.position') }}",
                        "tilt": "{{ states('sensor.tilt') }}",
                        "set_cover_position": [],
                        "set_cover_tilt_position": [],
                        "open_cover": [],
                        "close_cover": [],
                    },
                },
            },
        )
    await async_trigger(hass, "sensor.trigger", "anything")

    state = hass.states.get("cover.test")
    assert state
    assert state.state == "opening"
    assert state.attributes["current_position"] == 50
    assert state.attributes["current_tilt_position"] == 49
