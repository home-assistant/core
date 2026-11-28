"""Tests for the EnOcean switch platform."""

from unittest.mock import Mock

from enocean_async import EURID
from enocean_async.protocol.erp1.rorg import RORG
from enocean_async.protocol.erp1.telegram import ERP1Telegram
import pytest
from pytest_homeassistant.common import MockConfigEntry, assert_setup_component

from homeassistant.components.enocean import DOMAIN
from homeassistant.components.enocean.entity import combine_hex
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import TelegramReceiver

SWITCH_CONFIG = {
    "switch": [
        {
            "platform": DOMAIN,
            "id": [0xDE, 0xAD, 0xBE, 0xEF],
            "channel": 1,
            "name": "room0",
        },
    ]
}


async def test_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test EnOcean switch ID migration."""

    entity_name = SWITCH_CONFIG["switch"][0]["name"]
    switch_entity_id = f"{SWITCH_DOMAIN}.{entity_name}"
    dev_id = SWITCH_CONFIG["switch"][0]["id"]
    channel = SWITCH_CONFIG["switch"][0]["channel"]

    old_unique_id = f"{combine_hex(dev_id)}"

    entry = MockConfigEntry(domain=DOMAIN, data={"device": "/dev/null"})

    entry.add_to_hass(hass)

    # Add a switch with an old unique_id to the entity registry
    entity_entry = entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=entry,
        original_name=entity_name,
    )

    assert entity_entry.entity_id == switch_entity_id
    assert entity_entry.unique_id == old_unique_id

    # Now add the sensor to check, whether the old unique_id is migrated

    with assert_setup_component(1, SWITCH_DOMAIN):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            SWITCH_CONFIG,
        )

    await hass.async_block_till_done()

    # Check that new entry has a new unique_id
    entity_entry = entity_registry.async_get(switch_entity_id)
    new_unique_id = f"{combine_hex(dev_id)}-{channel}"

    assert entity_entry.unique_id == new_unique_id
    assert (
        entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, old_unique_id)
        is None
    )


@pytest.mark.parametrize(
    ("rorg", "data", "expected_state"),
    [
        pytest.param(RORG.RORG_VLD, "046164", STATE_ON, id="actuator_status_on"),
        pytest.param(RORG.RORG_VLD, "046100", STATE_OFF, id="actuator_status_off"),
        pytest.param(RORG.RORG_VLD, "046264", STATE_OFF, id="other_channel"),
        pytest.param(RORG.RORG_4BS, "0000640c", STATE_ON, id="power_reading"),
    ],
)
async def test_status_telegram(
    hass: HomeAssistant,
    receive_telegram: TelegramReceiver,
    rorg: RORG,
    data: str,
    expected_state: str,
) -> None:
    """Test that telegrams of the actuator update the switch state."""
    assert await async_setup_component(hass, SWITCH_DOMAIN, SWITCH_CONFIG)
    await hass.async_block_till_done()

    await receive_telegram(
        ERP1Telegram(rorg, bytes.fromhex(data), EURID("DE:AD:BE:EF"))
    )

    assert hass.states.get("switch.room0").state == expected_state


@pytest.mark.usefixtures("receive_telegram")
@pytest.mark.parametrize(
    ("service", "expected_data"),
    [
        pytest.param(SERVICE_TURN_ON, "d20101640000000000", id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, "d20101000000000000", id="turn_off"),
    ],
)
async def test_switch_command(
    hass: HomeAssistant, mock_gateway: Mock, service: str, expected_data: str
) -> None:
    """Test that switching sends a command to the actuator."""
    assert await async_setup_component(hass, SWITCH_DOMAIN, SWITCH_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: "switch.room0"}, blocking=True
    )
    await hass.async_block_till_done()

    packet = mock_gateway.send_esp3_packet.call_args.args[0]
    assert packet.data == bytes.fromhex(expected_data)
    assert packet.optional == bytes.fromhex("03deadbeefff00")
