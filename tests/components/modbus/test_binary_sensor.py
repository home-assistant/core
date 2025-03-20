"""Thetests for the Modbus sensor component."""

import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_DEVICE_ADDRESS,
    CONF_INPUT_TYPE,
    CONF_SLAVE_COUNT,
    CONF_VIRTUAL_COUNT,
    MODBUS_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_UNIQUE_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult

ENTITY_ID = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
SLAVE_UNIQUE_ID = "ground_floor_sensor"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                    CONF_DEVICE_CLASS: "door",
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DEVICE_ADDRESS: 10,
                    CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                    CONF_DEVICE_CLASS: "door",
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DEVICE_ADDRESS: 10,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                }
            ]
        },
    ],
)
async def test_config_binary_sensor(hass: HomeAssistant, mock_modbus) -> None:
    """Run config test for binary sensor."""
    assert SENSOR_DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                },
            ],
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                },
            ],
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                },
            ],
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("register_words", "do_exception", "expected"),
    [
        (
            [True] * 8,
            False,
            STATE_ON,
        ),
        (
            [False] * 8,
            False,
            STATE_OFF,
        ),
        (
            [False] + [True] * 7,
            False,
            STATE_OFF,
        ),
        (
            [True] + [False] * 7,
            False,
            STATE_ON,
        ),
        (
            [False] * 8,
            True,
            STATE_UNAVAILABLE,
        ),
        (
            [1] * 8,
            False,
            STATE_ON,
        ),
        (
            [2] * 8,
            False,
            STATE_OFF,
        ),
        (
            [4] + [1] * 7,
            False,
            STATE_OFF,
        ),
        (
            [1] + [8] * 7,
            False,
            STATE_ON,
        ),
    ],
)
async def test_all_binary_sensor(hass: HomeAssistant, expected, mock_do_cycle) -> None:
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
    ],
)
async def test_service_binary_sensor_update(
    hass: HomeAssistant, mock_modbus_ha
) -> None:
    """Run test for service homeassistant.update_entity."""

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_modbus_ha.read_coils.return_value = ReadResult([0x01])
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


ENTITY_ID2 = f"{ENTITY_ID}_1"


@pytest.mark.parametrize(
    "mock_test_state",
    [
        (
            State(ENTITY_ID, STATE_ON),
            State(ENTITY_ID2, STATE_OFF),
        )
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SCAN_INTERVAL: 0,
                    CONF_VIRTUAL_COUNT: 1,
                }
            ]
        },
    ],
)
async def test_restore_state_binary_sensor(
    hass: HomeAssistant, mock_test_state, mock_modbus
) -> None:
    """Run test for binary sensor restore state."""
    assert hass.states.get(ENTITY_ID).state == mock_test_state[0].state
    assert hass.states.get(ENTITY_ID2).state == mock_test_state[1].state


TEST_NAME = "test_sensor"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE_COUNT: 3,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 52,
                    CONF_VIRTUAL_COUNT: 3,
                }
            ]
        },
    ],
)
async def test_config_virtual_binary_sensor(hass: HomeAssistant, mock_modbus) -> None:
    """Run config test for binary sensor."""
    assert SENSOR_DOMAIN in hass.config.components

    for addon in ("", " 1", " 2", " 3"):
        entity_id = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}{addon}".replace(" ", "_")
        assert hass.states.get(entity_id) is not None


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                }
            ]
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words", "expected", "slaves"),
    [
        (
            {CONF_SLAVE_COUNT: 1, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [False] * 8,
            STATE_OFF,
            [STATE_OFF],
        ),
        (
            {CONF_VIRTUAL_COUNT: 1, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [False] * 8,
            STATE_OFF,
            [STATE_OFF],
        ),
        (
            {CONF_SLAVE_COUNT: 1, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [True] + [False] * 7,
            STATE_ON,
            [STATE_OFF],
        ),
        (
            {CONF_VIRTUAL_COUNT: 1, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [True] + [False] * 7,
            STATE_ON,
            [STATE_OFF],
        ),
        (
            {CONF_SLAVE_COUNT: 1, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [False, True] + [False] * 6,
            STATE_OFF,
            [STATE_ON],
        ),
        (
            {CONF_VIRTUAL_COUNT: 1, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [False, True] + [False] * 6,
            STATE_OFF,
            [STATE_ON],
        ),
        (
            {CONF_SLAVE_COUNT: 7, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [True, False] * 4,
            STATE_ON,
            [STATE_OFF, STATE_ON] * 3 + [STATE_OFF],
        ),
        (
            {CONF_VIRTUAL_COUNT: 7, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [True, False] * 4,
            STATE_ON,
            [STATE_OFF, STATE_ON] * 3 + [STATE_OFF],
        ),
        (
            {CONF_SLAVE_COUNT: 31, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [True, False] * 16,
            STATE_ON,
            [STATE_OFF, STATE_ON] * 15 + [STATE_OFF],
        ),
        (
            {CONF_VIRTUAL_COUNT: 31, CONF_UNIQUE_ID: SLAVE_UNIQUE_ID},
            [True, False] * 16,
            STATE_ON,
            [STATE_OFF, STATE_ON] * 15 + [STATE_OFF],
        ),
    ],
)
async def test_virtual_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    expected,
    slaves,
    mock_do_cycle,
) -> None:
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected

    for i, slave in enumerate(slaves):
        entity_id = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}_{i + 1}".replace(" ", "_")
        assert hass.states.get(entity_id).state == slave
        unique_id = f"{SLAVE_UNIQUE_ID}_{i + 1}"
        entry = entity_registry.async_get(entity_id)
        assert entry.unique_id == unique_id


async def test_no_discovery_info_binary_sensor(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert SENSOR_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {CONF_PLATFORM: MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert SENSOR_DOMAIN in hass.config.components
