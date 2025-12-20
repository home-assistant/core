"""Test KNX number."""

from homeassistant.components.knx.const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from homeassistant.components.knx.schema import TextSchema
from homeassistant.components.text import TextMode
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, State

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import mock_restore_cache


async def test_text(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX text."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            TextSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )
    # set value
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.test", "value": "hello world"},
        blocking=True,
    )
    await knx.assert_write(
        test_address,
        (
            0x68,
            0x65,
            0x6C,
            0x6C,
            0x6F,
            0x20,
            0x77,
            0x6F,
            0x72,
            0x6C,
            0x64,
            0x0,
            0x0,
            0x0,
        ),
    )
    state = hass.states.get("text.test")
    assert state.state == "hello world"

    # update from KNX
    await knx.receive_write(
        test_address,
        (0x68, 0x61, 0x6C, 0x6C, 0x6F, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0),
    )
    state = hass.states.get("text.test")
    assert state.state == "hallo"


async def test_text_restore_and_respond(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX text with passive_address, restoring state and respond_to_read."""
    test_address = "1/1/1"
    test_passive_address = "3/3/3"

    fake_state = State("text.test", "test test")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            TextSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("text.test")
    assert state.state == "test test"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(
        test_address,
        (0x74, 0x65, 0x73, 0x74, 0x20, 0x74, 0x65, 0x73, 0x74, 0x0, 0x0, 0x0, 0x0, 0x0),
    )

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()

    # update from KNX passive address
    await knx.receive_write(
        test_passive_address,
        (0x68, 0x61, 0x6C, 0x6C, 0x6F, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0),
    )
    state = hass.states.get("text.test")
    assert state.state == "hallo"


async def test_text_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a text."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.TEXT,
        entity_data={"name": "test"},
        knx_data={
            "ga_text": {"write": "1/1/1", "dpt": "16.000"},
            "mode": TextMode.PASSWORD,
            "sync_state": True,
        },
    )
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.test", "value": "hallo"},
        blocking=True,
    )
    await knx.assert_write(
        "1/1/1",
        (0x68, 0x61, 0x6C, 0x6C, 0x6F, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0),
    )
    knx.assert_state("text.test", "hallo", mode=TextMode.PASSWORD)


async def test_text_ui_load(knx: KNXTestKit) -> None:
    """Test loading a text from storage."""
    await knx.setup_integration(config_store_fixture="config_store_text.json")

    await knx.assert_read("2/2/2")
    await knx.receive_response(
        "2/2/2",
        (0x68, 0x61, 0x6C, 0x6C, 0x6F, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0),
    )
    knx.assert_state("text.test", "hallo", mode=TextMode.TEXT)
