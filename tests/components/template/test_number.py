"""The tests for the Template number platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import number
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE as NUMBER_ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE as NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.template import DOMAIN
from homeassistant.components.template.const import CONF_PICTURE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    async_get_flow_preview_state,
    async_trigger,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

TEST_AVAILABILITY_ENTITY_ID = "binary_sensor.test_availability"
TEST_MAXIMUM_ENTITY_ID = "sensor.maximum"
TEST_MINIMUM_ENTITY_ID = "sensor.minimum"
TEST_STATE_ENTITY_ID = "number.test_state"
TEST_STEP_ENTITY_ID = "sensor.step"
TEST_NUMBER = TemplatePlatformSetup(
    number.DOMAIN,
    None,
    "template_number",
    make_test_trigger(
        TEST_AVAILABILITY_ENTITY_ID,
        TEST_MAXIMUM_ENTITY_ID,
        TEST_MINIMUM_ENTITY_ID,
        TEST_STATE_ENTITY_ID,
        TEST_STEP_ENTITY_ID,
    ),
)
TEST_SET_VALUE_ACTION = {
    "action": "test.automation",
    "data": {
        "action": "set_value",
        "caller": "{{ this.entity_id }}",
        "value": "{{ value }}",
    },
}
TEST_REQUIRED = {"state": "0", "step": "1", "set_value": []}


@pytest.fixture
async def setup_number(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of number integration."""
    await setup_entity(hass, TEST_NUMBER, style, count, config)


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": "number",
            "state": "{{ 10 }}",
            "min": 0,
            "max": 100,
            "step": 0.1,
            "set_value": {
                "action": "input_number.set_value",
                "target": {"entity_id": "input_number.test"},
                "data": {"value": "{{ value }}"},
            },
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("number.my_template")
    assert state is not None
    assert state == snapshot


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ 4 }}",
                "set_value": {"service": "script.set_value"},
                "step": "{{ 1 }}",
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_number")
async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    _verify(hass, 4, 1, 0.0, 100.0, None)


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            0,
            {
                "state": "{{ 4 }}",
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_number")
async def test_missing_required_keys(hass: HomeAssistant) -> None:
    """Test: missing required fields will fail."""
    assert hass.states.async_all("number") == []


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ 4 }}",
                "set_value": {"service": "script.set_value"},
                "min": "{{ 3 }}",
                "max": "{{ 5 }}",
                "step": "{{ 1 }}",
                "unit_of_measurement": "beer",
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_number")
async def test_all_optional_config(hass: HomeAssistant) -> None:
    """Test: including all optional templates is ok."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    _verify(hass, 4, 1, 3, 5, "beer")


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": f"{{{{ states('{TEST_STATE_ENTITY_ID}') | float(1.0) }}}}",
                "step": f"{{{{ states('{TEST_STEP_ENTITY_ID}') | float(5.0) }}}}",
                "min": f"{{{{ states('{TEST_MINIMUM_ENTITY_ID}') | float(0.0) }}}}",
                "max": f"{{{{ states('{TEST_MAXIMUM_ENTITY_ID}') | float(100.0) }}}}",
                "set_value": [TEST_SET_VALUE_ACTION],
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_number")
async def test_template_number(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls: list[ServiceCall]
) -> None:
    """Test templates with values from other entities."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, 4)
    await async_trigger(hass, TEST_STEP_ENTITY_ID, 1)
    await async_trigger(hass, TEST_MINIMUM_ENTITY_ID, 3)
    await async_trigger(hass, TEST_MAXIMUM_ENTITY_ID, 5)
    _verify(hass, 4, 1, 3, 5, None)

    await async_trigger(hass, TEST_STATE_ENTITY_ID, 5)
    _verify(hass, 5, 1, 3, 5, None)

    await async_trigger(hass, TEST_STEP_ENTITY_ID, 2)
    _verify(hass, 5, 2, 3, 5, None)

    await async_trigger(hass, TEST_MINIMUM_ENTITY_ID, 2)
    _verify(hass, 5, 2, 2, 5, None)

    await async_trigger(hass, TEST_MAXIMUM_ENTITY_ID, 6)
    _verify(hass, 5, 2, 2, 6, None)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {CONF_ENTITY_ID: TEST_NUMBER.entity_id, NUMBER_ATTR_VALUE: 2},
        blocking=True,
    )

    # Check this variable can be used in set_value script
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_value"
    assert calls[-1].data["caller"] == TEST_NUMBER.entity_id
    assert calls[-1].data["value"] == 2

    await async_trigger(hass, TEST_STATE_ENTITY_ID, 2)
    _verify(hass, 2, 2, 2, 6, None)


def _verify(
    hass: HomeAssistant,
    expected_value: int,
    expected_step: int,
    expected_minimum: int,
    expected_maximum: int,
    expected_unit_of_measurement: str | None,
) -> None:
    """Verify number's state."""
    state = hass.states.get(TEST_NUMBER.entity_id)
    attributes = state.attributes
    assert state.state == str(float(expected_value))
    assert attributes.get(ATTR_STEP) == float(expected_step)
    assert attributes.get(ATTR_MAX) == float(expected_maximum)
    assert attributes.get(ATTR_MIN) == float(expected_minimum)
    assert attributes.get(CONF_UNIT_OF_MEASUREMENT) == expected_unit_of_measurement


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "initial_expected_state"),
    [(ConfigurationStyle.MODERN, ""), (ConfigurationStyle.TRIGGER, None)],
)
@pytest.mark.parametrize(
    ("config", "attribute", "expected"),
    [
        (
            {
                CONF_ICON: "{% if states.number.test_state.state == '1' %}mdi:check{% endif %}",
                **TEST_REQUIRED,
            },
            ATTR_ICON,
            "mdi:check",
        ),
        (
            {
                CONF_PICTURE: "{% if states.number.test_state.state == '1' %}check.jpg{% endif %}",
                **TEST_REQUIRED,
            },
            ATTR_ENTITY_PICTURE,
            "check.jpg",
        ),
    ],
)
@pytest.mark.usefixtures("setup_number")
async def test_templated_optional_config(
    hass: HomeAssistant,
    attribute: str,
    expected: str,
    initial_expected_state: str | None,
) -> None:
    """Test optional config templates."""
    state = hass.states.get(TEST_NUMBER.entity_id)
    assert state.attributes.get(attribute) == initial_expected_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "1")

    state = hass.states.get(TEST_NUMBER.entity_id)

    assert state.attributes[attribute] == expected


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for number template."""

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
            "template_type": "number",
            "state": "{{ 10 }}",
            "min": 0,
            "max": 100,
            "step": 0.1,
            "set_value": {
                "action": "input_number.set_value",
                "target": {"entity_id": "input_number.test"},
                "data": {"value": "{{ value }}"},
            },
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("number.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "set_value": [],
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_number")
async def test_optimistic(hass: HomeAssistant) -> None:
    """Test configuration with optimistic state."""
    await hass.services.async_call(
        number.DOMAIN,
        number.SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TEST_NUMBER.entity_id, "value": 4},
        blocking=True,
    )

    state = hass.states.get(TEST_NUMBER.entity_id)
    assert float(state.state) == 4

    await hass.services.async_call(
        number.DOMAIN,
        number.SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TEST_NUMBER.entity_id, "value": 2},
        blocking=True,
    )

    state = hass.states.get(TEST_NUMBER.entity_id)
    assert float(state.state) == 2


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ states('sensor.test_state') }}",
                "optimistic": False,
                "set_value": [],
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_number")
async def test_not_optimistic(hass: HomeAssistant) -> None:
    """Test optimistic yaml option set to false."""
    await hass.services.async_call(
        number.DOMAIN,
        number.SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TEST_NUMBER.entity_id, "value": 4},
        blocking=True,
    )

    state = hass.states.get(TEST_NUMBER.entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "set_value": [],
                "state": "{{ states('number.test_state') }}",
                "availability": "{{ is_state('binary_sensor.test_availability', 'on') }}",
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_number")
async def test_availability(hass: HomeAssistant) -> None:
    """Test configuration with optimistic state."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "4.0")
    await async_trigger(hass, TEST_AVAILABILITY_ENTITY_ID, "on")
    state = hass.states.get(TEST_NUMBER.entity_id)
    assert float(state.state) == 4

    await async_trigger(hass, TEST_AVAILABILITY_ENTITY_ID, "off")

    state = hass.states.get(TEST_NUMBER.entity_id)
    assert state.state == STATE_UNAVAILABLE

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "2.0")

    state = hass.states.get(TEST_NUMBER.entity_id)
    assert state.state == STATE_UNAVAILABLE

    await async_trigger(hass, TEST_AVAILABILITY_ENTITY_ID, "on")

    state = hass.states.get(TEST_NUMBER.entity_id)
    assert float(state.state) == 2


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ 1 }}",
                "set_value": [],
                "step": "{{ 1 }}",
                "optimistic": True,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.MODERN,
    ],
)
@pytest.mark.usefixtures("setup_number")
async def test_empty_action_config(hass: HomeAssistant) -> None:
    """Test configuration with empty script."""
    await hass.services.async_call(
        number.DOMAIN,
        number.SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TEST_NUMBER.entity_id, "value": 4},
        blocking=True,
    )

    state = hass.states.get(TEST_NUMBER.entity_id)
    assert float(state.state) == 4


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        number.DOMAIN,
        {
            "name": "My template",
            "min": 0.0,
            "max": 100.0,
            **TEST_REQUIRED,
        },
    )

    assert state["state"] == "0.0"


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
) -> None:
    """Test unique_id option only creates one vacuum per id."""
    await setup_and_test_unique_id(hass, TEST_NUMBER, style, TEST_REQUIRED, "{{ 0 }}")


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to vacuum unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_NUMBER, style, entity_registry, TEST_REQUIRED, "{{ 0 }}"
    )
