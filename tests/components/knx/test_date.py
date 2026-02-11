"""Test KNX date."""

from homeassistant.components.date import (
    ATTR_DATE,
    DOMAIN as DATE_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.knx.const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from homeassistant.components.knx.schema import DateSchema
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, State

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import mock_restore_cache


async def test_date(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX date."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            DateSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )
    # set value
    await hass.services.async_call(
        DATE_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": "date.test", ATTR_DATE: "1999-03-31"},
        blocking=True,
    )
    await knx.assert_write(
        test_address,
        (0x1F, 0x03, 0x63),
    )
    state = hass.states.get("date.test")
    assert state.state == "1999-03-31"

    # update from KNX
    await knx.receive_write(
        test_address,
        (0x01, 0x02, 0x03),
    )
    state = hass.states.get("date.test")
    assert state.state == "2003-02-01"


async def test_date_restore_and_respond(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX date with passive_address, restoring state and respond_to_read."""
    test_address = "1/1/1"
    test_passive_address = "3/3/3"

    fake_state = State("date.test", "2023-07-24")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            DateSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("date.test")
    assert state.state == "2023-07-24"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(
        test_address,
        (0x18, 0x07, 0x17),
    )

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()

    # update from KNX passive address
    await knx.receive_write(
        test_passive_address,
        (0x18, 0x02, 0x18),
    )
    state = hass.states.get("date.test")
    assert state.state == "2024-02-24"


async def test_date_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a date entity."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.DATE,
        entity_data={"name": "test"},
        knx_data={
            "ga_date": {"write": "0/0/1", "state": "0/0/2"},
            "respond_to_read": True,
            "sync_state": True,
        },
    )
    # created entity sends a read-request to the read address
    await knx.assert_read("0/0/2", response=(0x18, 0x02, 0x18))
    knx.assert_state("date.test", "2024-02-24")


async def test_date_ui_load(knx: KNXTestKit) -> None:
    """Test loading date entities from storage."""
    await knx.setup_integration(config_store_fixture="config_store_date.json")

    # date_with_state_address
    await knx.assert_read("0/0/2", response=(0x18, 0x02, 0x18), ignore_order=True)

    knx.assert_state(
        "date.date_with_state_address",
        "2024-02-24",
    )
    knx.assert_state(
        "date.date_without_state_address",
        "unknown",
    )
