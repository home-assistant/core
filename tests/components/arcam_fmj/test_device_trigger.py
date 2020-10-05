"""The tests for Arcam FMJ Receiver control device triggers."""
import pytest

from homeassistant.components.arcam_fmj.const import DOMAIN
import homeassistant.components.automation as automation
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
    """Test we get the expected triggers from a arcam_fmj."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "host", 1234)},
    )
    entity_reg.async_get_or_create(
        "media_player", DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": "media_player.arcam_fmj_5678",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_turn_on_request(hass, calls, player_setup, state):
    """Test for turn_on and turn_off triggers firing."""
    state.get_power.return_value = None

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
                        "entity_id": player_setup,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{ trigger.entity_id }}"},
                    },
                }
            ]
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": player_setup},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == player_setup
