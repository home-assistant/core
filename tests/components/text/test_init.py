"""The tests for the text component."""

from typing import Any

import pytest
from pytest_homeassistant.common import (
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache_with_extra_data,
    setup_test_component_platform,
)

from homeassistant.components.text import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_PATTERN,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
    TextMode,
)
from homeassistant.components.text.services import _async_set_value
from homeassistant.const import ATTR_ENTITY_ID, MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component

from .common import MockRestoreText, MockTextEntity


async def test_text_default(hass: HomeAssistant) -> None:
    """Test text entity with defaults."""
    text = MockTextEntity()
    text.hass = hass

    assert text.capability_attributes == {
        ATTR_MIN: 0,
        ATTR_MAX: MAX_LENGTH_STATE_STATE,
        ATTR_MODE: TextMode.TEXT,
        ATTR_PATTERN: None,
    }
    assert text.pattern is None
    assert text.state == "test"


async def test_text_new_min_max_pattern(hass: HomeAssistant) -> None:
    """Test text entity with new min, max, and pattern."""
    text = MockTextEntity(native_min=-1, native_max=500, pattern=r"[a-z]")
    text.hass = hass

    assert text.capability_attributes == {
        ATTR_MIN: 0,
        ATTR_MAX: MAX_LENGTH_STATE_STATE,
        ATTR_MODE: TextMode.TEXT,
        ATTR_PATTERN: r"[a-z]",
    }


async def test_text_set_value(hass: HomeAssistant) -> None:
    """Test text entity with set_value service."""
    text = MockTextEntity(native_min=1, native_max=5, pattern=r"[a-z]")
    text.hass = hass

    await _async_set_value(
        text, ServiceCall(hass, DOMAIN, SERVICE_SET_VALUE, {ATTR_VALUE: "test2"})
    )

    assert text.state == "test2"


@pytest.mark.parametrize(
    ("value", "translation_key", "message"),
    [
        pytest.param(
            "",
            "value_too_short",
            "Value  for text.test is too short (minimum length 1)",
            id="too_short",
        ),
        pytest.param(
            "hello world!",
            "value_too_long",
            "Value hello world! for text.test is too long (maximum length 5)",
            id="too_long",
        ),
        pytest.param(
            "HELLO",
            "value_pattern_mismatch",
            "Value HELLO for text.test doesn't match pattern [a-z]",
            id="pattern_mismatch",
        ),
    ],
)
async def test_text_set_value_invalid(
    hass: HomeAssistant, value: str, translation_key: str, message: str
) -> None:
    """Test set_value service raises a translated error for invalid values."""
    entity = MockTextEntity(native_min=1, native_max=5, pattern=r"[a-z]")
    entity._attr_name = "Test"
    setup_test_component_platform(hass, DOMAIN, [entity])
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "test"}})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "text.test", ATTR_VALUE: value},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert str(exc_info.value) == message
    assert hass.states.get("text.test").state == "test"


async def test_text_value_outside_bounds(hass: HomeAssistant) -> None:
    """Test text entity with value that is outside min and max."""
    with pytest.raises(ValueError):
        _ = MockTextEntity(
            "hello world", native_min=2, native_max=5, pattern=r"[a-z]"
        ).state
    with pytest.raises(ValueError):
        _ = MockTextEntity(
            "hello world", native_min=15, native_max=20, pattern=r"[a-z]"
        ).state


RESTORE_DATA = {
    "native_max": 5,
    "native_min": 1,
    # "mode": TextMode.TEXT,
    # "pattern": r"[A-Za-z0-9]",
    "native_value": "Hello",
}


async def test_restore_number_save_state(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test RestoreNumber."""
    entity0 = MockRestoreText(
        name="Test",
        native_max=5,
        native_min=1,
        native_value="Hello",
    )
    setup_test_component_platform(hass, DOMAIN, [entity0])

    assert await async_setup_component(hass, DOMAIN, {"text": {"platform": "test"}})
    await hass.async_block_till_done()

    # Trigger saving state
    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == entity0.entity_id
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == RESTORE_DATA
    assert isinstance(extra_data["native_value"], str)


@pytest.mark.parametrize(
    ("native_max", "native_min", "native_value", "native_value_type", "extra_data"),
    [
        (5, 1, "Hello", str, RESTORE_DATA),
        (255, 1, None, type(None), None),
        (255, 1, None, type(None), {}),
        (255, 1, None, type(None), {"beer": 123}),
        (255, 1, None, type(None), {"native_value": {}}),
    ],
)
async def test_restore_number_restore_state(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    native_max,
    native_min,
    native_value,
    native_value_type,
    extra_data,
) -> None:
    """Test RestoreNumber."""
    mock_restore_cache_with_extra_data(hass, ((State("text.test", ""), extra_data),))

    entity0 = MockRestoreText(
        native_max=native_max,
        native_min=native_min,
        name="Test",
        native_value=None,
    )
    setup_test_component_platform(hass, DOMAIN, [entity0])

    assert await async_setup_component(hass, DOMAIN, {"text": {"platform": "test"}})
    await hass.async_block_till_done()

    assert hass.states.get(entity0.entity_id)

    assert entity0.native_max == native_max
    assert entity0.native_min == native_min
    assert entity0.mode == TextMode.TEXT
    assert entity0.pattern is None
    assert entity0.native_value == native_value
    assert isinstance(entity0.native_value, native_value_type)
