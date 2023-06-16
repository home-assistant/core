"""Test conversation triggers."""
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Initialize components."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})


async def test_if_fires_on_event(hass: HomeAssistant, calls, setup_comp) -> None:
    """Test the firing of events."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": [
                        "Hey yo",
                        "Ha ha ha",
                    ],
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"data": "{{ trigger }}"},
                },
            }
        },
    )

    await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "Ha ha ha",
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["data"] == {
        "alias": None,
        "id": "0",
        "idx": "0",
        "platform": "conversation",
        "sentence": "Ha ha ha",
    }
