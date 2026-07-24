"""Test reproduce state for Number entities."""

import pytest

from homeassistant.components.number.const import (
    ATTR_MAX,
    ATTR_MIN,
    DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service

VALID_NUMBER1 = "19.0"
VALID_NUMBER2 = "99.9"


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Number states."""

    hass.states.async_set(
        "number.test_number", VALID_NUMBER1, {ATTR_MIN: 5, ATTR_MAX: 100}
    )

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("number.test_number", VALID_NUMBER1),
            # Should not raise
            State("number.non_existing", "234"),
        ],
    )

    assert hass.states.get("number.test_number").state == VALID_NUMBER1

    # Test reproducing with different state
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_VALUE)
    await async_reproduce_state(
        hass,
        [
            State("number.test_number", VALID_NUMBER2),
            # Should not raise
            State("number.non_existing", "234"),
        ],
    )

    assert len(calls) == 1
    assert calls[0].domain == DOMAIN
    assert calls[0].data == {"entity_id": "number.test_number", "value": VALID_NUMBER2}

    # Test invalid state
    await async_reproduce_state(hass, [State("number.test_number", "invalid_state")])

    assert len(calls) == 1
