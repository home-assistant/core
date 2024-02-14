"""The tests for WebOS TV automation triggers."""
from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.components.webostv import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import async_get as get_dev_reg
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import ENTITY_ID, FAKE_UUID

from tests.common import MockEntity, MockEntityPlatform


async def test_webostv_turn_on_trigger_device_id(
    hass: HomeAssistant, calls, client
) -> None:
    """Test for turn_on triggers by device_id firing."""
    await setup_webostv(hass)

    device_reg = get_dev_reg(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "webostv.turn_on",
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

    with patch("homeassistant.config.load_yaml_dict", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    calls.clear()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_webostv_turn_on_trigger_entity_id(
    hass: HomeAssistant, calls, client
) -> None:
    """Test for turn_on triggers by entity_id firing."""
    await setup_webostv(hass)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "webostv.turn_on",
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
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, client
) -> None:
    """Test wrong trigger platform type."""
    await setup_webostv(hass)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "webostv.wrong_type",
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
        "ValueError: Unknown webOS Smart TV trigger platform webostv.wrong_type"
        in caplog.text
    )


async def test_trigger_invalid_entity_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, client
) -> None:
    """Test turn on trigger using invalid entity_id."""
    await setup_webostv(hass)

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
                        "platform": "webostv.turn_on",
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
        f"ValueError: Entity {invalid_entity} is not a valid webostv entity"
        in caplog.text
    )
