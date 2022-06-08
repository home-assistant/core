"""The tests for the Number component."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
    NumberDeviceClass,
    NumberEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PLATFORM,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM


class MockDefaultNumberEntity(NumberEntity):
    """Mock NumberEntity device to use in tests."""

    @property
    def value(self):
        """Return the current value."""
        return 0.5


class MockNumberEntity(NumberEntity):
    """Mock NumberEntity device to use in tests."""

    @property
    def max_value(self) -> float:
        """Return the max value."""
        return 1.0

    @property
    def value(self):
        """Return the current value."""
        return 0.5


async def test_step(hass: HomeAssistant) -> None:
    """Test the step calculation."""
    number = MockDefaultNumberEntity()
    number.hass = hass
    assert number.step == 1.0

    number_2 = MockNumberEntity()
    number_2.hass = hass
    assert number_2.step == 0.1


async def test_sync_set_value(hass: HomeAssistant) -> None:
    """Test if async set_value calls sync set_value."""
    number = MockDefaultNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    await number.async_set_value(42)

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 42


async def test_set_value(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test we can only set valid values."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "50.0"
    assert state.attributes.get(ATTR_STEP) == 1.0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 60.0, ATTR_ENTITY_ID: "number.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "60.0"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 110.0, ATTR_ENTITY_ID: "number.test"},
            blocking=True,
        )

    await hass.async_block_till_done()
    state = hass.states.get("number.test")
    assert state.state == "60.0"


async def test_deprecated_attributes(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test entity using deprecated attributes."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init(empty=True)
    platform.ENTITIES.append(platform.LegacyMockNumberEntity())
    entity = platform.ENTITIES[0]
    entity._attr_name = "Test"
    entity._attr_max_value = 25
    entity._attr_min_value = -25
    entity._attr_step = 2.5
    entity._attr_value = 51.0

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "51.0"
    assert state.attributes.get(ATTR_MAX) == 25.0
    assert state.attributes.get(ATTR_MIN) == -25.0
    assert state.attributes.get(ATTR_STEP) == 2.5

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0.0, ATTR_ENTITY_ID: "number.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "0.0"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 110.0, ATTR_ENTITY_ID: "number.test"},
            blocking=True,
        )

    await hass.async_block_till_done()
    state = hass.states.get("number.test")
    assert state.state == "0.0"


async def test_deprecated_methods(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test entity using deprecated methods."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.LegacyMockNumberEntity(
            name="Test",
            max_value=25.0,
            min_value=-25.0,
            step=2.5,
            value=51.0,
        )
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "51.0"
    assert state.attributes.get(ATTR_MAX) == 25.0
    assert state.attributes.get(ATTR_MIN) == -25.0
    assert state.attributes.get(ATTR_STEP) == 2.5

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0.0, ATTR_ENTITY_ID: "number.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "0.0"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 110.0, ATTR_ENTITY_ID: "number.test"},
            blocking=True,
        )

    await hass.async_block_till_done()
    state = hass.states.get("number.test")
    assert state.state == "0.0"


@pytest.mark.parametrize(
    "unit_system, native_unit, state_unit, initial_native_value, initial_state_value, "
    "updated_native_value, updated_state_value, native_max_value, state_max_value, "
    "native_min_value, state_min_value, native_step, state_step",
    [
        (
            IMPERIAL_SYSTEM,
            TEMP_FAHRENHEIT,
            TEMP_FAHRENHEIT,
            100,
            100,
            50,
            50,
            140,
            140,
            -9,
            -9,
            3,
            3,
        ),
        (
            IMPERIAL_SYSTEM,
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
            38,
            100,
            10,
            50,
            60,
            140,
            -23,
            -10,
            3,
            3,
        ),
        (
            METRIC_SYSTEM,
            TEMP_FAHRENHEIT,
            TEMP_CELSIUS,
            100,
            38,
            50,
            10,
            140,
            60,
            -9,
            -23,
            3,
            3,
        ),
        (
            METRIC_SYSTEM,
            TEMP_CELSIUS,
            TEMP_CELSIUS,
            38,
            38,
            10,
            10,
            60,
            60,
            -23,
            -23,
            3,
            3,
        ),
    ],
)
async def test_temperature_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    state_unit,
    initial_native_value,
    initial_state_value,
    updated_native_value,
    updated_state_value,
    native_max_value,
    state_max_value,
    native_min_value,
    state_min_value,
    native_step,
    state_step,
):
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockNumberEntity(
            name="Test",
            native_max_value=native_max_value,
            native_min_value=native_min_value,
            native_step=native_step,
            native_unit_of_measurement=native_unit,
            native_value=initial_native_value,
            device_class=NumberDeviceClass.TEMPERATURE,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(initial_state_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit
    assert state.attributes[ATTR_MAX] == state_max_value
    assert state.attributes[ATTR_MIN] == state_min_value
    assert state.attributes[ATTR_STEP] == state_step

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: updated_state_value, ATTR_ENTITY_ID: entity0.entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(updated_state_value))
    assert entity0._values["native_value"] == updated_native_value

    # Set to the minimum value
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: state_min_value, ATTR_ENTITY_ID: entity0.entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(state_min_value), rel=0.1)

    # Set to the maximum value
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: state_max_value, ATTR_ENTITY_ID: entity0.entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(state_max_value), rel=0.1)
