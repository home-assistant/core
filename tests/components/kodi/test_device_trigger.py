"""The tests for Kodi device triggers."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.kodi import DOMAIN
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import init_integration

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


@pytest.fixture
async def kodi_media_player(hass):
    """Get a kodi media player."""
    await init_integration(hass)
    return f"{MP_DOMAIN}.name"


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a kodi."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "host", 1234)},
    )
    entity_entry = entity_registry.async_get_or_create(
        MP_DOMAIN, DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for trigger in ["turn_off", "turn_on"]
    ]

    # Test triggers are either kodi specific triggers or media_player entity triggers
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    for expected_trigger in expected_triggers:
        assert expected_trigger in triggers
    for trigger in triggers:
        assert trigger in expected_triggers or trigger["domain"] == "media_player"


async def test_if_fires_on_state_change(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls, kodi_media_player
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    entry = entity_registry.async_get(kodi_media_player)

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
                            "some": (
                                "turn_on - {{ trigger.entity_id }} - {{ trigger.id}}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": entry.device_id,
                        "entity_id": entry.id,
                        "type": "turn_off",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_off - {{ trigger.entity_id }} - {{ trigger.id}}"
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        "turn_on",
        {"entity_id": kodi_media_player},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == f"turn_on - {kodi_media_player} - 0"

    await hass.services.async_call(
        MP_DOMAIN,
        "turn_off",
        {"entity_id": kodi_media_player},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == f"turn_off - {kodi_media_player} - 0"


async def test_if_fires_on_state_change_legacy(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls, kodi_media_player
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    entry = entity_registry.async_get(kodi_media_player)

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
                            "some": (
                                "turn_on - {{ trigger.entity_id }} - {{ trigger.id}}"
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        "turn_on",
        {"entity_id": kodi_media_player},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == f"turn_on - {kodi_media_player} - 0"
