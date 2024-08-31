"""Test reproduce state for Text entities."""

import pytest

from homeassistant.components.text.const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_PATTERN,
    DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service

VALID_TEXT1 = "Hello"
VALID_TEXT2 = "World"


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Text states."""

    hass.states.async_set(
        "text.test_text",
        VALID_TEXT1,
        {ATTR_MIN: 1, ATTR_MAX: 5, ATTR_MODE: "text", ATTR_PATTERN: None},
    )

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("text.test_text", VALID_TEXT1),
            # Should not raise
            State("text.non_existing", "234"),
        ],
    )

    assert hass.states.get("text.test_text").state == VALID_TEXT1

    # Test reproducing with different state
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_VALUE)
    await async_reproduce_state(
        hass,
        [
            State("text.test_text", VALID_TEXT2),
            # Should not raise
            State("text.non_existing", "234"),
        ],
    )

    assert len(calls) == 1
    assert calls[0].domain == DOMAIN
    assert calls[0].data == {"entity_id": "text.test_text", "value": VALID_TEXT2}
