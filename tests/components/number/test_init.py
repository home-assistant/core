"""The tests for the Number component."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.number import (
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
    NumberEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


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
    assert number.step == 1.0

    number_2 = MockNumberEntity()
    assert number_2.step == 0.1


async def test_sync_set_value(hass: HomeAssistant) -> None:
    """Test if async set_value calls sync set_value."""
    number = MockDefaultNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    await number.async_set_value(42)

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 42


async def test_custom_integration_and_validation(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
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

    hass.states.async_set("number.test", 60.0)
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
