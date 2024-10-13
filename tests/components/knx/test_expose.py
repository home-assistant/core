"""Test KNX expose."""

from datetime import timedelta

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.knx import CONF_KNX_EXPOSE, DOMAIN, KNX_ADDRESS
from homeassistant.components.knx.schema import ExposeSchema
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_ENTITY_ID,
    CONF_TYPE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import async_fire_time_changed


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

    # Change state to on
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", True)

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {"brightness": 180})
    await hass.async_block_till_done()
    await knx.assert_no_telegram()

    # Change attribute and state
    hass.states.async_set(entity_id, "off", {"brightness": 0})
    await hass.async_block_till_done()
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

    # Before init no response shall be sent
    await knx.receive_read("1/1/8")
    await knx.assert_telegram_count(0)

    # Change state to "on"; no attribute
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    await knx.assert_telegram_count(0)

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (1,))

    # Read in between
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (1,))

    # Change state keep attribute
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await hass.async_block_till_done()
    await knx.assert_telegram_count(0)

    # Change state and attribute
    hass.states.async_set(entity_id, "on", {attribute: 0})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (0,))

    # Change state to "off"; no attribute
    hass.states.async_set(entity_id, "off", {})
    await hass.async_block_till_done()
    await knx.assert_telegram_count(0)

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (1,))

    # Change state to "off"; null attribute
    hass.states.async_set(entity_id, "off", {attribute: None})
    await hass.async_block_till_done()
    await knx.assert_telegram_count(0)

    # Ignore "unavailable" state
    hass.states.async_set(entity_id, "unavailable", {attribute: None})
    await hass.async_block_till_done()
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

    # Before init default value shall be sent as response
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (0,))

    # Change state to "on"; no attribute -> default
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (0,))

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (1,))

    # Change state keep attribute
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await hass.async_block_till_done()
    await knx.assert_no_telegram()

    # Use default for "unavailable" state
    hass.states.async_set(entity_id, "unavailable")
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (0,))

    # Change state and attribute
    hass.states.async_set(entity_id, "on", {attribute: 3})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (3,))

    # Read in between
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (3,))

    # Change state to "off"; no attribute
    hass.states.async_set(entity_id, "off", {})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (0,))

    # Change state and attribute
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (1,))

    # Change state to "off"; null attribute
    hass.states.async_set(entity_id, "off", {attribute: None})
    await hass.async_block_till_done()
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
    await hass.async_block_till_done()
    await knx.assert_write(
        "1/1/8", (84, 104, 105, 115, 32, 105, 115, 32, 97, 32, 118, 101, 114, 121)
    )


async def test_expose_cooldown(
    hass: HomeAssistant, knx: KNXTestKit, freezer: FrozenDateTimeFactory
) -> None:
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
    # Change state to 1
    hass.states.async_set(entity_id, "1", {})
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (1,))
    # Change state to 2 - skip because of cooldown
    hass.states.async_set(entity_id, "2", {})
    await hass.async_block_till_done()
    await knx.assert_no_telegram()

    # Change state to 3
    hass.states.async_set(entity_id, "3", {})
    await hass.async_block_till_done()
    await knx.assert_no_telegram()
    # Wait for cooldown to pass
    freezer.tick(timedelta(seconds=cooldown_time))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await knx.assert_write("1/1/8", (3,))


async def test_expose_value_template(
    hass: HomeAssistant, knx: KNXTestKit, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an expose with value_template."""
    entity_id = "fake.entity"
    attribute = "brightness"
    binary_address = "1/1/1"
    percent_address = "2/2/2"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: [
                {
                    CONF_TYPE: "binary",
                    KNX_ADDRESS: binary_address,
                    CONF_ENTITY_ID: entity_id,
                    CONF_VALUE_TEMPLATE: "{{ not value == 'on' }}",
                },
                {
                    CONF_TYPE: "percentU8",
                    KNX_ADDRESS: percent_address,
                    CONF_ENTITY_ID: entity_id,
                    CONF_ATTRIBUTE: attribute,
                    CONF_VALUE_TEMPLATE: "{{ 255 - value }}",
                },
            ]
        },
    )

    # Change attribute to 0
    hass.states.async_set(entity_id, "on", {attribute: 0})
    await hass.async_block_till_done()
    await knx.assert_write(binary_address, False)
    await knx.assert_write(percent_address, (255,))

    # Change attribute to 255
    hass.states.async_set(entity_id, "off", {attribute: 255})
    await hass.async_block_till_done()
    await knx.assert_write(binary_address, True)
    await knx.assert_write(percent_address, (0,))

    # Change attribute to null (eg. light brightness)
    hass.states.async_set(entity_id, "off", {attribute: None})
    await hass.async_block_till_done()
    # without explicit `None`-handling or default value this fails with
    # TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'
    assert "Error rendering value template for KNX expose" in caplog.text


@pytest.mark.parametrize(
    "invalid_attribute",
    [
        101.0,
        "invalid",  # can't cast to float
    ],
)
async def test_expose_conversion_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    knx: KNXTestKit,
    invalid_attribute: str,
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

    # Before init default value shall be sent as response
    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", (3,))

    caplog.clear()
    # Change attribute: Expect no exception
    hass.states.async_set(
        entity_id,
        "on",
        {attribute: invalid_attribute},
    )
    await hass.async_block_till_done()
    await knx.assert_no_telegram()
    assert (
        f'Could not expose fake.entity fake_attribute value "{invalid_attribute}" to KNX:'
        in caplog.text
    )


@freeze_time("2022-1-7 9:13:14")
@pytest.mark.parametrize(
    ("time_type", "raw"),
    [
        ("time", (0xA9, 0x0D, 0x0E)),  # localtime includes day of week
        ("date", (0x07, 0x01, 0x16)),
        ("datetime", (0x7A, 0x1, 0x7, 0xA9, 0xD, 0xE, 0x20, 0xC0)),
    ],
)
async def test_expose_with_date(
    hass: HomeAssistant, knx: KNXTestKit, time_type: str, raw: tuple[int, ...]
) -> None:
    """Test an expose with a date."""
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: time_type,
                KNX_ADDRESS: "1/1/8",
            }
        }
    )

    await knx.assert_write("1/1/8", raw)

    await knx.receive_read("1/1/8")
    await knx.assert_response("1/1/8", raw)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
