"""Test KNX expose."""
from datetime import timedelta
import time
from unittest.mock import patch

from homeassistant.components.knx import CONF_KNX_EXPOSE, DOMAIN, KNX_ADDRESS
from homeassistant.components.knx.schema import ExposeSchema
from homeassistant.const import CONF_ATTRIBUTE, CONF_ENTITY_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .conftest import KNXTestKit

from tests.common import async_fire_time_changed_exact


async def test_binary_expose(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test a binary expose to only send telegrams on state change."""
    entity_id = "fake.entity"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "binary",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
            }
        },
    )
    assert not hass.states.async_all()

    # Change state to on
    hass.states.async_set(entity_id, "on", {})
    await knx.assert_write("1/1/8", True)

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {"brightness": 180})
    await knx.assert_no_telegram()

    # Change attribute and state
    hass.states.async_set(entity_id, "off", {"brightness": 0})
    await knx.assert_write("1/1/8", False)


async def test_expose_attribute(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test an expose to only send telegrams on attribute change."""
    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                CONF_ATTRIBUTE: attribute,
            }
        },
    )
    assert not hass.states.async_all()

    # Before init no response shall be sent
    await knx.receive_read("1/1/8")
    await knx.assert_telegram_count(0)

    # Change state to "on"; no attribute
    hass.states.async_set(entity_id, "on", {})
    await knx.assert_telegram_count(0)

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await knx.assert_write("1/1/8", (1,))

    # Read in between
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (1,))

    # Change state keep attribute
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await knx.assert_telegram_count(0)

    # Change state and attribute
    hass.states.async_set(entity_id, "on", {attribute: 0})
    await knx.assert_write("1/1/8", (0,))

    # Change state to "off"; no attribute
    hass.states.async_set(entity_id, "off", {})
    await knx.assert_telegram_count(0)


async def test_expose_attribute_with_default(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test an expose to only send telegrams on attribute change."""
    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                CONF_ATTRIBUTE: attribute,
                ExposeSchema.CONF_KNX_EXPOSE_DEFAULT: 0,
            }
        },
    )
    assert not hass.states.async_all()

    # Before init default value shall be sent as response
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (0,))

    # Change state to "on"; no attribute
    hass.states.async_set(entity_id, "on", {})
    await knx.assert_write("1/1/8", (0,))

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await knx.assert_write("1/1/8", (1,))

    # Change state keep attribute
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await knx.assert_no_telegram()

    # Change state and attribute
    hass.states.async_set(entity_id, "on", {attribute: 3})
    await knx.assert_write("1/1/8", (3,))

    # Read in between
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (3,))

    # Change state to "off"; no attribute
    hass.states.async_set(entity_id, "off", {})
    await knx.assert_write("1/1/8", (0,))


async def test_expose_string(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test an expose to send string values of up to 14 bytes only."""

    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "string",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                CONF_ATTRIBUTE: attribute,
                ExposeSchema.CONF_KNX_EXPOSE_DEFAULT: "Test",
            }
        },
    )
    assert not hass.states.async_all()

    # Before init default value shall be sent as response
    await knx.receive_read("1/1/8")
    await knx.assert_response(
        "1/1/8", (84, 101, 115, 116, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    )

    # Change attribute; keep state
    hass.states.async_set(
        entity_id,
        "on",
        {attribute: "This is a very long string that is larger than 14 bytes"},
    )
    await knx.assert_write(
        "1/1/8", (84, 104, 105, 115, 32, 105, 115, 32, 97, 32, 118, 101, 114, 121)
    )


async def test_expose_cooldown(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test an expose with cooldown."""
    cooldown_time = 2
    entity_id = "fake.entity"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                ExposeSchema.CONF_KNX_EXPOSE_COOLDOWN: cooldown_time,
            }
        },
    )
    assert not hass.states.async_all()
    # Change state to 1
    hass.states.async_set(entity_id, "1", {})
    await knx.assert_write("1/1/8", (1,))
    # Change state to 2 - skip because of cooldown
    hass.states.async_set(entity_id, "2", {})
    await knx.assert_no_telegram()

    # Change state to 3
    hass.states.async_set(entity_id, "3", {})
    await knx.assert_no_telegram()
    # Wait for cooldown to pass
    async_fire_time_changed_exact(hass, dt.utcnow() + timedelta(seconds=cooldown_time))
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (3,))


async def test_expose_conversion_exception(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test expose throws exception."""

    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percent",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                CONF_ATTRIBUTE: attribute,
                ExposeSchema.CONF_KNX_EXPOSE_DEFAULT: 1,
            }
        },
    )
    assert not hass.states.async_all()

    # Before init default value shall be sent as response
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (3,))

    # Change attribute: Expect no exception
    hass.states.async_set(
        entity_id,
        "on",
        {attribute: 101},
    )

    await knx.assert_no_telegram()


@patch("time.localtime")
async def test_expose_with_date(
    localtime, hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test an expose with a date."""
    localtime.return_value = time.struct_time([2022, 1, 7, 9, 13, 14, 6, 0, 0])
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "datetime",
                KNX_ADDRESS: "1/1/8",
            }
        }
    )
    assert not hass.states.async_all()

    await knx.assert_write("1/1/8", (0x7A, 0x1, 0x7, 0xE9, 0xD, 0xE, 0x20, 0x80))

    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (0x7A, 0x1, 0x7, 0xE9, 0xD, 0xE, 0x20, 0x80))

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
