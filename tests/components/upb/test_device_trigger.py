"""The tests for Universal Powerline Bus (UPB) device triggers."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.upb.const import DOMAIN, TRIGGER_TYPES
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a upb."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "host", 1234)},
    )
    entity_reg.async_get_or_create("scene", DOMAIN, "4224", device_id=device_entry.id)
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "goto",
            "device_id": device_entry.id,
            "entity_id": f"scene.upb_4224",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "activated",
            "device_id": device_entry.id,
            "entity_id": f"scene.upb_4224",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "deactivated",
            "device_id": device_entry.id,
            "entity_id": f"scene.upb_4224",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "blink",
            "device_id": device_entry.id,
            "entity_id": f"scene.upb_4224",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "fade_started",
            "device_id": device_entry.id,
            "entity_id": f"scene.upb_4224",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "fade_stopped",
            "device_id": device_entry.id,
            "entity_id": f"scene.upb_4224",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


@pytest.mark.parametrize("typ", [*TRIGGER_TYPES])
async def test_if_fires_on_activate_request(typ, hass, calls, element, upb_link):
    """Test for activate triggers firing."""

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "upb.entity42",
                        "type": typ,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"warm kitty": "{{ trigger.entity_id }}"},
                    },
                },
            ]
        },
    )

    upb_link.entity_id = "upb.entity42"
    # pylint: disable: protected-access
    upb_link._element_changed(element, {"last_change": {"command": typ}})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["warm kitty"] == "upb.entity42"
