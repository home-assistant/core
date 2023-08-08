"""The tests for WebOS TV automation triggers."""
from unittest.mock import Mock, call, patch

from panasonic_viera import Keys
import pytest

from homeassistant.components import automation
from homeassistant.components.panasonic_viera import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as get_dev_reg
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockEntity, MockEntityPlatform

ENTITY_ID = "media_player.panasonic_viera_tv"
FAKE_UUID = "mock-unique-id"


async def test_panasonic_viera_turn_on_trigger_device_id(
    hass: HomeAssistant, init_integration: MockConfigEntry, calls, mock_remote: Mock
) -> None:
    """Test for turn_on triggers by device_id firing."""

    device_reg = get_dev_reg(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "panasonic_viera.turn_on",
                        "device_id": device.id,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": device.id,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == device.id
    assert calls[0].data["id"] == 0

    with patch("homeassistant.config.load_yaml", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    calls.clear()
    await hass.services.async_call(
        "media_player",
        "turn_off",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    await hass.async_block_till_done()
    power = getattr(Keys.power, "value", Keys.power)
    assert mock_remote.send_key.call_args_list == [call(power)]
    assert len(calls) == 0


async def test_panasonic_viera_turn_on_trigger_entity_id(
    hass: HomeAssistant, init_integration: MockConfigEntry, calls
) -> None:
    """Test for turn_on triggers by entity_id firing."""

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "panasonic_viera.turn_on",
                        "entity_id": ENTITY_ID,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == ENTITY_ID
    assert calls[0].data["id"] == 0


async def test_wrong_trigger_platform_type(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test wrong trigger platform type."""

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "panasonic_viera.wrong_type",
                        "entity_id": ENTITY_ID,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    assert (
        "ValueError: Unknown webOS Smart TV trigger platform panasonic_viera.wrong_type"
        in caplog.text
    )


async def test_trigger_invalid_entity_id(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test turn on trigger using invalid entity_id."""

    platform = MockEntityPlatform(hass)

    invalid_entity = f"{DOMAIN}.invalid"
    await platform.async_add_entities([MockEntity(name=invalid_entity)])

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "panasonic_viera.turn_on",
                        "entity_id": invalid_entity,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    assert (
        f"ValueError: Entity {invalid_entity} is not a valid panasonic_viera entity"
        in caplog.text
    )
