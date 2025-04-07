"""The tests for the Demo component."""

from collections.abc import Generator
import json
from unittest.mock import patch

import pytest

from homeassistant.components.demo import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_history(hass: HomeAssistant) -> None:
    """Mock history component loaded."""
    hass.config.components.add("history")


@pytest.fixture(autouse=True)
def mock_device_tracker_update_config() -> Generator[None]:
    """Prevent device tracker from creating known devices file."""
    with patch("homeassistant.components.device_tracker.legacy.update_config"):
        yield


async def test_setting_up_demo(mock_history: None, hass: HomeAssistant) -> None:
    """Test if we can set up the demo and dump it to JSON."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await hass.async_start()

    # This is done to make sure entity components don't accidentally store
    # non-JSON-serializable data in the state machine.
    try:
        json.dumps(hass.states.async_all(), cls=JSONEncoder)
    except Exception:  # noqa: BLE001
        pytest.fail(
            "Unable to convert all demo entities to JSON. Wrong data in state machine!"
        )
