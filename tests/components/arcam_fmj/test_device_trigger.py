"""The tests for Arcam FMJ Receiver control device triggers."""
import pytest

from homeassistant.components.arcam_fmj.const import DOMAIN
import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a arcam_fmj."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "host", 1234)},
    )
    entity_entry = entity_registry.async_get_or_create(
        "media_player", DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )

    # Test triggers are either arcam_fmj specific or media_player entity triggers
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    for expected_trigger in expected_triggers:
        assert expected_trigger in triggers
    for trigger in triggers:
        assert trigger in expected_triggers or trigger["domain"] == "media_player"


async def test_if_fires_on_turn_on_request(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls, player_setup, state
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    entry = entity_registry.async_get(player_setup)

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
                        "device_id": entry.device_id,
                        "entity_id": entry.id,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.entity_id }}",
                            "id": "{{ trigger.id }}",
                        },
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
    assert calls[0].data["id"] == 0


async def test_if_fires_on_turn_on_request_legacy(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls, player_setup, state
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    entry = entity_registry.async_get(player_setup)

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
                        "device_id": entry.device_id,
                        "entity_id": entry.entity_id,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.entity_id }}",
                            "id": "{{ trigger.id }}",
                        },
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
    assert calls[0].data["id"] == 0
