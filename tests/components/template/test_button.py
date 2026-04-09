"""The tests for the Template button platform."""

import datetime as dt
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.template import DOMAIN
from homeassistant.components.template.const import CONF_PICTURE
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    async_trigger,
    make_test_action,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry

TEST_ATTRIBUTE_ENTITY_ID = "sensor.test_attribute"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"
TEST_BUTTON = TemplatePlatformSetup(BUTTON_DOMAIN, None, "template_button", {})
PRESS_ACTION = make_test_action("press")


@pytest.fixture
async def setup_button(hass: HomeAssistant, count: int, config: dict[str, Any]) -> None:
    """Do setup of button integration."""
    await setup_entity(hass, TEST_BUTTON, ConfigurationStyle.MODERN, count, config)


@pytest.fixture
async def setup_single_attribute_button(
    hass: HomeAssistant,
    attribute: str,
    attribute_template: str,
    config: dict,
) -> None:
    """Do setup of button integration with a single attribute."""
    await setup_entity(
        hass,
        TEST_BUTTON,
        ConfigurationStyle.MODERN,
        1,
        config,
        extra_config={attribute: attribute_template}
        if attribute and attribute_template
        else {},
    )


def _verify(
    hass: HomeAssistant,
    expected_value: str,
    attributes: dict[str, Any] | None = None,
    entity_id: str = TEST_BUTTON.entity_id,
) -> None:
    """Verify button's state."""
    attributes = attributes or {}
    if CONF_FRIENDLY_NAME not in attributes:
        attributes[CONF_FRIENDLY_NAME] = TEST_BUTTON.object_id
    state = hass.states.get(entity_id)
    assert state.state == expected_value
    assert state.attributes == attributes


@pytest.mark.parametrize(
    "config_entry_extra_options",
    [
        {},
        {
            "device_class": "update",
        },
    ],
)
async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry_extra_options: dict[str, str],
) -> None:
    """Test the config flow."""

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "button",
            "press": [
                {
                    "service": "input_boolean.toggle",
                    "metadata": {},
                    "data": {},
                    "target": {"entity_id": "input_boolean.test"},
                }
            ],
        }
        | config_entry_extra_options,
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.my_template")
    assert state is not None
    assert state == snapshot


@pytest.mark.parametrize(("count", "config"), [(1, PRESS_ACTION)])
@pytest.mark.usefixtures("setup_button")
async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    _verify(hass, STATE_UNKNOWN)


@pytest.mark.parametrize(("count", "config"), [(1, {"press": []})])
@pytest.mark.usefixtures("setup_button")
async def test_missing_emtpy_press_action_config(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test: missing optional template is ok."""
    _verify(hass, STATE_UNKNOWN)

    now = dt.datetime.now(dt.UTC)
    freezer.move_to(now)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {CONF_ENTITY_ID: TEST_BUTTON.entity_id},
        blocking=True,
    )

    _verify(
        hass,
        now.isoformat(),
    )


@pytest.mark.parametrize(("count", "config"), [(0, {})])
@pytest.mark.usefixtures("setup_button")
async def test_missing_required_keys(hass: HomeAssistant) -> None:
    """Test: missing required fields will fail."""
    assert hass.states.async_all("button") == []


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                **PRESS_ACTION,
                "device_class": "restart",
            },
        )
    ],
)
@pytest.mark.usefixtures("setup_button")
async def test_device_class_option(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    calls: list[ServiceCall],
) -> None:
    """Test optional options is ok."""
    _verify(
        hass,
        STATE_UNKNOWN,
        {
            CONF_DEVICE_CLASS: "restart",
            CONF_FRIENDLY_NAME: TEST_BUTTON.object_id,
        },
        TEST_BUTTON.entity_id,
    )

    now = dt.datetime.now(dt.UTC)
    freezer.move_to(now)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {CONF_ENTITY_ID: TEST_BUTTON.entity_id},
        blocking=True,
    )

    assert_action(TEST_BUTTON, calls, 1, "press")
    _verify(
        hass,
        now.isoformat(),
        {
            CONF_DEVICE_CLASS: "restart",
            CONF_FRIENDLY_NAME: TEST_BUTTON.object_id,
        },
        TEST_BUTTON.entity_id,
    )


@pytest.mark.parametrize("config", [PRESS_ACTION])
@pytest.mark.parametrize(
    ("attribute", "attribute_template", "attribute_name", "expected"),
    [
        (
            CONF_ICON,
            "{{ 'mdi:test' if is_state('sensor.test_attribute', 'on') else '' }}",
            ATTR_ICON,
            "mdi:test",
        ),
        (
            CONF_PICTURE,
            "{{ 'test.jpg' if is_state('sensor.test_attribute', 'on') else '' }}",
            ATTR_ENTITY_PICTURE,
            "test.jpg",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_button")
async def test_options_that_are_templates(
    hass: HomeAssistant,
    attribute_name: str,
    expected: str,
    freezer: FrozenDateTimeFactory,
    calls: list[ServiceCall],
) -> None:
    """Test button options that are templates."""
    expected_attributes = {attribute_name: expected}

    _verify(hass, STATE_UNKNOWN, {attribute_name: ""})

    await async_trigger(hass, TEST_ATTRIBUTE_ENTITY_ID, STATE_ON)

    _verify(hass, STATE_UNKNOWN, expected_attributes)

    now = dt.datetime.now(dt.UTC)
    freezer.move_to(now)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {CONF_ENTITY_ID: TEST_BUTTON.entity_id},
        blocking=True,
    )

    assert_action(TEST_BUTTON, calls, 1, "press")
    _verify(hass, now.isoformat(), expected_attributes)


@pytest.mark.parametrize("config", [PRESS_ACTION])
@pytest.mark.parametrize(
    ("attribute", "attribute_template"), [("name", "Button {{ 1 + 1 }}")]
)
@pytest.mark.usefixtures("setup_single_attribute_button")
async def test_name_template(hass: HomeAssistant) -> None:
    """Test: name template."""
    _verify(
        hass,
        STATE_UNKNOWN,
        {
            CONF_FRIENDLY_NAME: "Button 2",
        },
        "button.button_2",
    )


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one button per id."""
    await setup_and_test_unique_id(
        hass, TEST_BUTTON, ConfigurationStyle.MODERN, PRESS_ACTION
    )


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template unique_id propagates to button unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_BUTTON, ConfigurationStyle.MODERN, entity_registry, PRESS_ACTION
    )


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for button template."""

    device_config_entry = MockConfigEntry()
    device_config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("test", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    await hass.async_block_till_done()
    assert device_entry is not None
    assert device_entry.id is not None

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "button",
            "device_id": device_entry.id,
            "press": [
                {
                    "service": "input_boolean.toggle",
                    "metadata": {},
                    "data": {},
                    "target": {"entity_id": "input_boolean.test"},
                }
            ],
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("button.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize(
    ("config", "attribute", "attribute_template"),
    [
        (
            PRESS_ACTION,
            "availability",
            "{{ is_state('binary_sensor.availability', 'on') }}",
        )
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_button")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""

    await async_trigger(hass, TEST_AVAILABILITY_ENTITY, STATE_ON)

    # Device State should not be unavailable
    assert hass.states.get(TEST_BUTTON.entity_id).state != STATE_UNAVAILABLE

    # When Availability template returns false
    await async_trigger(hass, TEST_AVAILABILITY_ENTITY, STATE_OFF)

    # device state should be unavailable
    assert hass.states.get(TEST_BUTTON.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("config", "attribute", "attribute_template"),
    [(PRESS_ACTION, "availability", "{{ x - 12 }}")],
)
@pytest.mark.usefixtures("setup_single_attribute_button")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get(TEST_BUTTON.entity_id).state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text
