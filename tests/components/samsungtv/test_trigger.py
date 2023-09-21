"""The tests for WebOS TV automation triggers."""
from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.components.samsungtv import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_samsungtv_entry
from .test_media_player import ENTITY_ID, MOCK_ENTRYDATA_ENCRYPTED_WS

from tests.common import MockEntity, MockEntityPlatform


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_turn_on_trigger_device_id(
    hass: HomeAssistant, calls: list[ServiceCall], device_registry: dr.DeviceRegistry
) -> None:
    """Test for turn_on triggers by device_id firing."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "any")})
    assert device, repr(device_registry.devices)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "samsungtv.turn_on",
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
        "media_player", "turn_on", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == device.id
    assert calls[0].data["id"] == 0

    with patch("homeassistant.config.load_yaml", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    calls.clear()

    # Ensure WOL backup is called when trigger not present
    with patch(
        "homeassistant.components.samsungtv.media_player.send_magic_packet"
    ) as mock_send_magic_packet:
        await hass.services.async_call(
            "media_player", "turn_on", {"entity_id": ENTITY_ID}, blocking=True
        )
        await hass.async_block_till_done()

    assert len(calls) == 0
    mock_send_magic_packet.assert_called()


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_turn_on_trigger_entity_id(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for turn_on triggers by entity_id firing."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "samsungtv.turn_on",
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
        "media_player", "turn_on", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == ENTITY_ID
    assert calls[0].data["id"] == 0


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_wrong_trigger_platform_type(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test wrong trigger platform type."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "samsungtv.wrong_type",
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
        "ValueError: Unknown Samsung TV trigger platform samsungtv.wrong_type"
        in caplog.text
    )


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_trigger_invalid_entity_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test turn on trigger using invalid entity_id."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

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
                        "platform": "samsungtv.turn_on",
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
        f"ValueError: Entity {invalid_entity} is not a valid samsungtv entity"
        in caplog.text
    )
