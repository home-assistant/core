"""Test the my-PV water heater."""

from unittest.mock import AsyncMock, Mock

from my_pv.exceptions import MyPVConnectionError
import pytest

from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_OPERATION_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ELECTRIC,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_water_heater(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test successful setup of a water heater."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 54.3
    assert state.attributes[ATTR_MAX_TEMP] == 95
    assert state.attributes[ATTR_MIN_TEMP] == 5
    assert state.attributes[ATTR_TEMPERATURE] == 62.1


async def test_water_heater_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test turning the water heater off."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC

    mock_my_pv_client.is_on = False

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_OFF


async def test_water_heater_turn_off_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test turning off returns false."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC

    mock_my_pv_client.turn_off = AsyncMock(return_value=False)

    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC


async def test_water_heater_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test turning the water heater on."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )
    mock_my_pv_client.is_on = False

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_OFF

    mock_my_pv_client.is_on = True

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC


async def test_water_heater_turn_on_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test turning on returns false."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )
    mock_my_pv_client.is_on = False

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_OFF

    mock_my_pv_client.turn_on = AsyncMock(return_value=False)

    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_OFF


async def test_water_heater_set_operation_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting the operation mode to off."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC

    mock_my_pv_client.is_on = False

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
            ATTR_OPERATION_MODE: STATE_OFF,
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_OFF


async def test_water_heater_set_operation_electric(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting the operation mode to electric."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )
    mock_my_pv_client.is_on = False

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_OFF

    mock_my_pv_client.is_on = True

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
            ATTR_OPERATION_MODE: STATE_ELECTRIC,
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_ELECTRIC


async def test_water_heater_set_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting the target temperature."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 62.1

    mock_my_pv_client.target_temperature = 35

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
            ATTR_TEMPERATURE: 35,
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 35


async def test_water_heater_set_temp_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting the target temperature returns false."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_my_pv_client.set_target_temperature = AsyncMock(return_value=False)

    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
                ATTR_TEMPERATURE: 35,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 62.1


async def test_water_heater_set_temp_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test connection error when setting the target temperature."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_my_pv_client.set_target_temperature.side_effect = MyPVConnectionError()

    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "water_heater.my_pv_ac_elwa_2",
                ATTR_TEMPERATURE: 35,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 62.1
