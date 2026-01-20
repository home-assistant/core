"""Test KNX number."""

from typing import Any

import pytest

from homeassistant.components.knx.const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from homeassistant.components.knx.schema import NumberSchema
from homeassistant.const import CONF_NAME, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import mock_restore_cache_with_extra_data


async def test_number_set_value(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX number with passive_address and respond_to_read restoring state."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            NumberSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                CONF_TYPE: "percent",
            }
        }
    )
    # set value
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.test", "value": 4.0},
        blocking=True,
    )
    await knx.assert_write(test_address, (0x0A,))
    state = hass.states.get("number.test")
    assert state.state == "4"
    assert state.attributes.get("unit_of_measurement") == "%"

    # set value out of range
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.test", "value": 101.0},
            blocking=True,
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.test", "value": -1},
            blocking=True,
        )
    await knx.assert_no_telegram()
    state = hass.states.get("number.test")
    assert state.state == "4"

    # update from KNX
    await knx.receive_write(test_address, (0xE6,))
    state = hass.states.get("number.test")
    assert state.state == "90"


async def test_number_restore_and_respond(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX number with passive_address and respond_to_read restoring state."""
    test_address = "1/1/1"
    test_passive_address = "3/3/3"

    RESTORE_DATA = {
        "native_max_value": None,  # Ignored by KNX number
        "native_min_value": None,  # Ignored by KNX number
        "native_step": None,  # Ignored by KNX number
        "native_unit_of_measurement": None,  # Ignored by KNX number
        "native_value": 160.0,
    }

    mock_restore_cache_with_extra_data(
        hass, ((State("number.test", "abc"), RESTORE_DATA),)
    )
    await knx.setup_integration(
        {
            NumberSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
                CONF_TYPE: "illuminance",
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("number.test")
    assert state.state == "160.0"
    assert state.attributes.get("unit_of_measurement") == "lx"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(test_address, (0x1F, 0xD0))

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()

    # update from KNX passive address
    await knx.receive_write(test_passive_address, (0x4E, 0xDE))
    state = hass.states.get("number.test")
    assert state.state == "9000.96"


@pytest.mark.parametrize(
    ("knx_config", "set_value", "expected_telegram", "expected_state"),
    [
        (
            {
                "ga_sensor": {
                    "write": "1/1/1",
                    "dpt": "5.001",  # percentU8
                },
            },
            50.0,
            (0x80,),
            {
                "state": "50",
                "device_class": None,
                "unit_of_measurement": "%",
                "min": 0,
                "max": 100,
                "step": 1,
            },
        ),
        (
            {
                "ga_sensor": {
                    "write": "1/1/1",
                    "dpt": "9.001",  # temperature 2 byte float
                    "passive": [],
                },
                "sync_state": True,
                "respond_to_read": True,
            },
            21.5,
            (0x0C, 0x33),
            {
                "state": "21.5",
                "device_class": "temperature",  # from DPT
                "unit_of_measurement": "°C",
                "min": -273.0,
                "max": 670760.0,
                "step": 0.01,
            },
        ),
    ],
)
async def test_number_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    knx_config: dict[str, Any],
    set_value: float,
    expected_telegram: tuple[int, ...],
    expected_state: dict[str, Any],
) -> None:
    """Test creating a number entity."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.NUMBER,
        entity_data={"name": "test"},
        knx_data=knx_config,
    )
    # set value
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.test", "value": set_value},
        blocking=True,
    )
    await knx.assert_write("1/1/1", expected_telegram)
    knx.assert_state("number.test", **expected_state)


async def test_number_ui_load(knx: KNXTestKit) -> None:
    """Test loading number entities from storage."""
    await knx.setup_integration(config_store_fixture="config_store_number.json")

    await knx.assert_read("2/0/0", response=(0x0B, 0xB8))  # 3000
    knx.assert_state(
        "number.test_simple",
        "0",  # 0 is default value
        unit_of_measurement="%",  # from DPT
        device_class=None,  # default values
        mode="auto",
        min=0,
        max=100,
        step=1,
    )
    knx.assert_state(
        "number.test_options",
        "3000",
        unit_of_measurement="kW",
        device_class="power",
        min=3000,
        max=5000,
        step=100,
        mode="slider",
    )
