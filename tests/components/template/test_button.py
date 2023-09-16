"""The tests for the Template button platform."""
import datetime as dt
from unittest.mock import patch

from homeassistant import setup
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.template.button import DEFAULT_NAME
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get

from tests.common import assert_setup_component

_TEST_BUTTON = "button.template_button"
_TEST_OPTIONS_BUTTON = "button.test"


async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "button": {
                        "press": {"service": "script.press"},
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN)


async def test_missing_required_keys(hass: HomeAssistant) -> None:
    """Test: missing required fields will fail."""
    with assert_setup_component(0, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {"template": {"button": {}}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("button") == []


async def test_all_optional_config(hass: HomeAssistant, calls) -> None:
    """Test: including all optional templates is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "test",
                    "button": {
                        "press": {
                            "service": "test.automation",
                            "data_template": {"caller": "{{ this.entity_id }}"},
                        },
                        "device_class": "restart",
                        "unique_id": "test",
                        "name": "test",
                        "icon": "mdi:test",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(
        hass,
        STATE_UNKNOWN,
        {
            CONF_DEVICE_CLASS: "restart",
            CONF_FRIENDLY_NAME: "test",
            CONF_ICON: "mdi:test",
        },
        _TEST_OPTIONS_BUTTON,
    )

    now = dt.datetime.now(dt.UTC)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {CONF_ENTITY_ID: _TEST_OPTIONS_BUTTON},
            blocking=True,
        )

    assert len(calls) == 1
    assert calls[0].data["caller"] == _TEST_OPTIONS_BUTTON

    _verify(
        hass,
        now.isoformat(),
        {
            CONF_DEVICE_CLASS: "restart",
            CONF_FRIENDLY_NAME: "test",
            CONF_ICON: "mdi:test",
        },
        _TEST_OPTIONS_BUTTON,
    )

    er = async_get(hass)
    assert er.async_get_entity_id("button", "template", "test-test")


async def test_name_template(hass: HomeAssistant) -> None:
    """Test: name template."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "button": {
                        "press": {"service": "script.press"},
                        "name": "Button {{ 1 + 1 }}",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(
        hass,
        STATE_UNKNOWN,
        {
            CONF_FRIENDLY_NAME: "Button 2",
        },
        "button.button_2",
    )


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test: unique id is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "test",
                    "button": {
                        "press": {"service": "script.press"},
                        "unique_id": "test",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN)


def _verify(
    hass,
    expected_value,
    attributes=None,
    entity_id=_TEST_BUTTON,
):
    """Verify button's state."""
    attributes = attributes or {}
    if CONF_FRIENDLY_NAME not in attributes:
        attributes[CONF_FRIENDLY_NAME] = DEFAULT_NAME
    state = hass.states.get(entity_id)
    assert state.state == expected_value
    assert state.attributes == attributes
