"""The tests for the Number component."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.number import ATTR_STEP, DOMAIN, NumberEntity
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from tests.common import mock_registry
from tests.testing_config.custom_components.test.number import UNIQUE_NUMBER

ATTR_VALUE = "value"
SERVICE_SET_VALUE = "set_value"


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


@pytest.fixture
def entity_reg(hass: HomeAssistant) -> entity_registry.EntityRegistry:
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_step(hass):
    """Test the step calculation."""
    number = MockDefaultNumberEntity()
    assert number.step == 1.0

    number_2 = MockNumberEntity()
    assert number_2.step == 0.1


async def test_sync_set_value(hass):
    """Test if async set_value calls sync set_value."""
    number = MockDefaultNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    await number.async_set_value(42)

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 42


async def test_custom_integration_and_validation(
    hass, entity_reg, enable_custom_integrations
):
    """Test we can only set valid values."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    reg_entry_1 = entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        UNIQUE_NUMBER,
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(reg_entry_1.entity_id)
    assert state.attributes.get(ATTR_VALUE) is None
    assert state.attributes.get(ATTR_STEP) == 1.0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 60.0, ATTR_ENTITY_ID: reg_entry_1.entity_id},
        blocking=True,
    )

    hass.states.async_set(reg_entry_1.entity_id, 60.0)
    await hass.async_block_till_done()
    state = hass.states.get(reg_entry_1.entity_id)
    assert state.state == "60.0"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 110.0, ATTR_ENTITY_ID: reg_entry_1.entity_id},
            blocking=True,
        )

    await hass.async_block_till_done()
    state = hass.states.get(reg_entry_1.entity_id)
    assert state.state == "60.0"
