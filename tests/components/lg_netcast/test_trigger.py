"""The tests for LG Netcast device triggers."""

from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.components.lg_netcast import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import ENTITY_ID, UNIQUE_ID, setup_lgnetcast

from tests.common import MockEntity, MockEntityPlatform


async def test_lg_netcast_turn_on_trigger_device_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for turn_on trigger by device_id firing."""
    await setup_lgnetcast(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, UNIQUE_ID)})
    assert device, repr(device_registry.devices)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "lg_netcast.turn_on",
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

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == device.id
    assert service_calls[1].data["id"] == 0

    with patch("homeassistant.config.load_yaml_dict", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    service_calls.clear()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_lg_netcast_turn_on_trigger_entity_id(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for turn_on triggers by entity firing."""
    await setup_lgnetcast(hass)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "lg_netcast.turn_on",
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

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == ENTITY_ID
    assert service_calls[1].data["id"] == 0


async def test_wrong_trigger_platform_type(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test wrong trigger platform type."""
    await setup_lgnetcast(hass)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "lg_netcast.wrong_type",
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
        "ValueError: Unknown LG Netcast TV trigger platform lg_netcast.wrong_type"
        in caplog.text
    )


async def test_trigger_invalid_entity_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test turn on trigger using invalid entity_id."""
    await setup_lgnetcast(hass)

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
                        "platform": "lg_netcast.turn_on",
                        "entity_id": invalid_entity,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                }
            ],
        },
    )

    assert (
        f"ValueError: Entity {invalid_entity} is not a valid lg_netcast entity"
        in caplog.text
    )
