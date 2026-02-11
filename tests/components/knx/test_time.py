"""Test KNX time."""

from homeassistant.components.knx.const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from homeassistant.components.knx.schema import TimeSchema
from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, State

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import mock_restore_cache


async def test_time(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX time."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            TimeSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )
    # set value
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": "time.test", ATTR_TIME: "01:02:03"},
        blocking=True,
    )
    await knx.assert_write(
        test_address,
        (0x01, 0x02, 0x03),
    )
    state = hass.states.get("time.test")
    assert state.state == "01:02:03"

    # update from KNX
    await knx.receive_write(
        test_address,
        (0x0C, 0x10, 0x3B),
    )
    state = hass.states.get("time.test")
    assert state.state == "12:16:59"


async def test_time_restore_and_respond(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX time with passive_address, restoring state and respond_to_read."""
    test_address = "1/1/1"
    test_passive_address = "3/3/3"

    fake_state = State("time.test", "01:02:03")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            TimeSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("time.test")
    assert state.state == "01:02:03"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(
        test_address,
        (0x01, 0x02, 0x03),
    )

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()

    # update from KNX passive address
    await knx.receive_write(
        test_passive_address,
        (0x0C, 0x00, 0x00),
    )
    state = hass.states.get("time.test")
    assert state.state == "12:00:00"


async def test_time_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a time entity."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.TIME,
        entity_data={"name": "test"},
        knx_data={
            "ga_time": {"write": "0/0/1", "state": "0/0/2"},
            "respond_to_read": True,
            "sync_state": True,
        },
    )
    # created entity sends a read-request to the read address
    await knx.assert_read("0/0/2", response=(0x01, 0x02, 0x03))
    knx.assert_state("time.test", "01:02:03")


async def test_time_ui_load(knx: KNXTestKit) -> None:
    """Test loading time entities from storage."""
    await knx.setup_integration(config_store_fixture="config_store_time.json")

    # time_with_state_address
    await knx.assert_read("0/0/2", response=(0x01, 0x02, 0x03), ignore_order=True)

    knx.assert_state(
        "time.time_with_state_address",
        "01:02:03",
    )
    knx.assert_state(
        "time.time_without_state_address",
        "unknown",
    )
