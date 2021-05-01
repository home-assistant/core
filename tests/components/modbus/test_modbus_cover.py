"""The tests for the Modbus cover component."""
import logging

import pytest

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CONF_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
)
from homeassistant.const import (
    CONF_COVERS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_CLOSED,
    STATE_OPEN,
)

from .conftest import ReadResult, base_config_test, base_test, run_service_update


@pytest.mark.parametrize(
    "do_options",
    [
        {},
        {
            CONF_SLAVE: 10,
            CONF_SCAN_INTERVAL: 20,
        },
    ],
)
@pytest.mark.parametrize("read_type", [CALL_TYPE_COIL, CONF_REGISTER])
async def test_config_cover(hass, do_options, read_type):
    """Run test for cover."""
    device_name = "test_cover"
    device_config = {
        CONF_NAME: device_name,
        read_type: 1234,
        **do_options,
    }
    await base_config_test(
        hass,
        device_config,
        device_name,
        COVER_DOMAIN,
        CONF_COVERS,
        None,
        method_discovery=True,
    )


@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0x00],
            STATE_CLOSED,
        ),
        (
            [0x80],
            STATE_CLOSED,
        ),
        (
            [0xFE],
            STATE_CLOSED,
        ),
        (
            [0xFF],
            STATE_OPEN,
        ),
        (
            [0x01],
            STATE_OPEN,
        ),
    ],
)
async def test_coil_cover(hass, regs, expected):
    """Run test for given config."""
    cover_name = "modbus_test_cover"
    state = await base_test(
        hass,
        {
            CONF_NAME: cover_name,
            CALL_TYPE_COIL: 1234,
            CONF_SLAVE: 1,
        },
        cover_name,
        COVER_DOMAIN,
        CONF_COVERS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0x00],
            STATE_CLOSED,
        ),
        (
            [0x80],
            STATE_OPEN,
        ),
        (
            [0xFE],
            STATE_OPEN,
        ),
        (
            [0xFF],
            STATE_OPEN,
        ),
        (
            [0x01],
            STATE_OPEN,
        ),
    ],
)
async def test_register_cover(hass, regs, expected):
    """Run test for given config."""
    cover_name = "modbus_test_cover"
    state = await base_test(
        hass,
        {
            CONF_NAME: cover_name,
            CONF_REGISTER: 1234,
            CONF_SLAVE: 1,
        },
        cover_name,
        COVER_DOMAIN,
        CONF_COVERS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize("read_type", [CALL_TYPE_COIL, CONF_REGISTER])
async def test_unsupported_config_cover(hass, read_type, caplog):
    """
    Run test for cover.

    Initialize the Cover in the legacy manner via platform.
    This test expects that the Cover won't be initialized, and that we get a config warning.
    """
    device_name = "test_cover"
    device_config = {CONF_NAME: device_name, read_type: 1234}

    caplog.set_level(logging.WARNING)
    caplog.clear()

    await base_config_test(
        hass,
        device_config,
        device_name,
        COVER_DOMAIN,
        CONF_COVERS,
        None,
        method_discovery=False,
        expect_init_to_fail=True,
    )

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"


async def test_service_cover_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    entity_id = "cover.test"
    config = {
        CONF_COVERS: [
            {
                CONF_NAME: "test",
                CONF_REGISTER: 1234,
                CONF_STATUS_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
            }
        ]
    }
    mock_pymodbus.read_holding_registers.return_value = ReadResult([0x00])
    await run_service_update(
        hass,
        config,
        entity_id,
    )
    assert hass.states.get(entity_id).state == STATE_CLOSED
    mock_pymodbus.read_holding_registers.return_value = ReadResult([0x01])
    await run_service_update(hass, config, entity_id, reuse=True)
    assert hass.states.get(entity_id).state == STATE_OPEN
