"""The tests for WebOS TV automation triggers."""

from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.const import SERVICE_RELOAD, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_samsungtv_entry
from .const import MOCK_ENTRYDATA_ENCRYPTED_WS

from tests.common import MockEntity, MockEntityPlatform


@pytest.mark.usefixtures("remoteencws", "rest_api")
@pytest.mark.parametrize("entity_domain", ["media_player", "remote"])
async def test_turn_on_trigger_device_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    entity_domain: str,
) -> None:
    """Test for turn_on triggers by device_id firing."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    entity_id = f"{entity_domain}.fake"

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "be9554b9-c9fb-41f4-8920-22da015376a4")}
    )
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
        entity_domain, SERVICE_TURN_ON, {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == device.id
    assert service_calls[1].data["id"] == 0

    with patch("homeassistant.config.load_yaml_dict", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    service_calls.clear()

    # Ensure WOL backup is called when trigger not present
    with patch(
        "homeassistant.components.samsungtv.entity.send_magic_packet"
    ) as mock_send_magic_packet:
        await hass.services.async_call(
            entity_domain, SERVICE_TURN_ON, {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

    assert len(service_calls) == 1
    mock_send_magic_packet.assert_called()


@pytest.mark.usefixtures("remoteencws", "rest_api")
@pytest.mark.parametrize("entity_domain", ["media_player", "remote"])
async def test_turn_on_trigger_entity_id(
    hass: HomeAssistant, service_calls: list[ServiceCall], entity_domain: str
) -> None:
    """Test for turn_on triggers by entity_id firing."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    entity_id = f"{entity_domain}.fake"

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "samsungtv.turn_on",
                        "entity_id": entity_id,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": entity_id,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        entity_domain, SERVICE_TURN_ON, {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == entity_id
    assert service_calls[1].data["id"] == 0


@pytest.mark.usefixtures("remoteencws", "rest_api")
@pytest.mark.parametrize("entity_domain", ["media_player", "remote"])
async def test_wrong_trigger_platform_type(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, entity_domain: str
) -> None:
    """Test wrong trigger platform type."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)
    entity_id = f"{entity_domain}.fake"

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "samsungtv.wrong_type",
                        "entity_id": entity_id,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": entity_id,
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
@pytest.mark.parametrize("entity_domain", ["media_player", "remote"])
async def test_trigger_invalid_entity_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, entity_domain: str
) -> None:
    """Test turn on trigger using invalid entity_id."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)
    entity_id = f"{entity_domain}.fake"

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
                            "some": entity_id,
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
