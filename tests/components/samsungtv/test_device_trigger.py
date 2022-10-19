"""The tests for samsung device triggers."""
from unittest.mock import patch

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.setup import async_setup_component

from . import setup_samsungtv_entry
from .test_media_player import MOCK_ENTRY_WS_WITH_MAC

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def device_reg(hass: HomeAssistant) -> device_registry.DeviceRegistry:
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass: HomeAssistant) -> entity_registry.EntityRegistry:
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.mark.usefixtures("rest_api")
async def test_get_triggers(
    hass: HomeAssistant,
    device_reg: device_registry.DeviceRegistry,
    entity_reg: entity_registry.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a samsungtv."""
    entity_id = f"{MP_DOMAIN}.{DOMAIN}_fake"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_WS_WITH_MAC,
        unique_id=entity_id,
    )
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "host")},
    )
    entity_reg.async_get_or_create(MP_DOMAIN, DOMAIN, "fake", device_id=device_entry.id)
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_id,
            "metadata": {"secondary": False},
        }
        for trigger in ["turn_off", "turn_on"]
    ]

    # Test triggers are either samsungtv specific triggers or media_player entity triggers
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    for expected_trigger in expected_triggers:
        assert expected_trigger in triggers
    for trigger in triggers:
        assert trigger in expected_triggers or trigger["domain"] == "media_player"


@pytest.mark.usefixtures("rest_api")
async def test_if_fires_on_state_change(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    await setup_samsungtv_entry(hass, MOCK_ENTRY_WS_WITH_MAC)
    entity_id = f"{MP_DOMAIN}.fake"

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
                        "entity_id": entity_id,
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
                        "device_id": "",
                        "entity_id": entity_id,
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

    with patch(
        "homeassistant.components.samsungtv.media_player.send_magic_packet"
    ) as mock_send_magic_packet:
        await hass.services.async_call(
            MP_DOMAIN,
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )
    assert mock_send_magic_packet.called

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == f"turn_on - {entity_id} - 0"

    await hass.services.async_call(
        MP_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == f"turn_off - {entity_id} - 0"
