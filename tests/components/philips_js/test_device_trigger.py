"""The tests for Philips TV device triggers."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.philips_js.const import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import (
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, mock_device):
    """Test we get the expected triggers."""
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "turn_on",
            "device_id": mock_device.id,
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", mock_device.id)
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_turn_on_request(
    hass, calls, mock_tv, mock_entity, mock_device
):
    """Test for turn_on and turn_off triggers firing."""

    mock_tv.on = False

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": mock_device.id,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.device_id }}",
                            "id": "{{ trigger.id}}",
                        },
                    },
                }
            ]
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": mock_entity},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == mock_device.id
    assert calls[0].data["id"] == 0
