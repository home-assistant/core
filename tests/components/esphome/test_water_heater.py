"""Test ESPHome water heaters."""

from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    WaterHeaterFeature,
    WaterHeaterInfo,
    WaterHeaterMode,
    WaterHeaterState,
    WaterHeaterStateFlag,
)
import pytest

from homeassistant.components.water_heater import (
    ATTR_AWAY_MODE,
    ATTR_OPERATION_LIST,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType


async def test_water_heater_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic water heater entity."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
            supported_modes=[
                WaterHeaterMode.ECO,
                WaterHeaterMode.GAS,
            ],
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            mode=WaterHeaterMode.ECO,
            current_temperature=45.0,
            target_temperature=50.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert state.state == "eco"
    assert state.attributes["current_temperature"] == 45.0
    assert state.attributes["temperature"] == 50.0
    assert state.attributes["min_temp"] == 10.0
    assert state.attributes["max_temp"] == 85.0
    assert state.attributes["operation_list"] == ["eco", "gas"]


async def test_water_heater_entity_no_modes(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a water heater entity without operation modes."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            current_temperature=45.0,
            target_temperature=50.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert state.attributes["min_temp"] == 10.0
    assert state.attributes["max_temp"] == 85.0
    assert state.attributes.get(ATTR_OPERATION_LIST) is None


async def test_water_heater_set_temperature(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test setting the target temperature."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            mode=WaterHeaterMode.ECO,
            target_temperature=45.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.test_my_boiler",
            ATTR_TEMPERATURE: 55,
        },
        blocking=True,
    )

    mock_client.water_heater_command.assert_has_calls(
        [call(key=1, target_temperature=55.0, device_id=0)]
    )


async def test_water_heater_set_operation_mode(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test setting the operation mode."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            supported_modes=[
                WaterHeaterMode.ECO,
                WaterHeaterMode.GAS,
            ],
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            mode=WaterHeaterMode.ECO,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.test_my_boiler",
            "operation_mode": "gas",
        },
        blocking=True,
    )

    mock_client.water_heater_command.assert_has_calls(
        [call(key=1, mode=WaterHeaterMode.GAS, device_id=0)]
    )


async def test_water_heater_on_off(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test turning the water heater on and off."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
            supported_features=WaterHeaterFeature.SUPPORTS_ON_OFF,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            target_temperature=50.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert state.attributes["supported_features"] & WaterHeaterEntityFeature.ON_OFF

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "water_heater.test_my_boiler"},
        blocking=True,
    )

    mock_client.water_heater_command.assert_has_calls(
        [call(key=1, on=True, device_id=0)]
    )

    mock_client.water_heater_command.reset_mock()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "water_heater.test_my_boiler"},
        blocking=True,
    )

    mock_client.water_heater_command.assert_has_calls(
        [call(key=1, on=False, device_id=0)]
    )


async def test_water_heater_target_temperature_step(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test target temperature step is respected."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
            target_temperature_step=5.0,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            target_temperature=50.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert state.attributes["target_temp_step"] == 5.0


async def test_water_heater_no_on_off_without_feature(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test ON_OFF feature is not set when not supported."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            target_temperature=50.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert not (
        state.attributes["supported_features"] & WaterHeaterEntityFeature.ON_OFF
    )


@pytest.mark.parametrize(
    ("supported_features", "has_away_mode"),
    [
        (WaterHeaterFeature.SUPPORTS_AWAY_MODE, True),
        (WaterHeaterFeature(0), False),
    ],
)
async def test_water_heater_away_mode_feature_flag(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
    supported_features: WaterHeaterFeature,
    has_away_mode: bool,
) -> None:
    """Test AWAY_MODE feature flag tracks the ESPHome SUPPORTS_AWAY_MODE flag."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
            supported_features=supported_features,
        )
    ]
    states = [WaterHeaterState(key=1, target_temperature=50.0)]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert (
        bool(
            state.attributes[ATTR_SUPPORTED_FEATURES]
            & WaterHeaterEntityFeature.AWAY_MODE
        )
        is has_away_mode
    )


@pytest.mark.parametrize(
    ("state_flag", "expected_away_mode"),
    [
        (WaterHeaterStateFlag(0), "off"),
        (WaterHeaterStateFlag.AWAY, "on"),
    ],
)
async def test_water_heater_away_mode_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
    state_flag: WaterHeaterStateFlag,
    expected_away_mode: str,
) -> None:
    """Test is_away_mode_on reflects the AWAY state flag."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
            supported_features=WaterHeaterFeature.SUPPORTS_AWAY_MODE,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            target_temperature=50.0,
            state=state_flag,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert state.attributes[ATTR_AWAY_MODE] == expected_away_mode


@pytest.mark.parametrize("away_mode", [True, False])
async def test_water_heater_set_away_mode(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
    away_mode: bool,
) -> None:
    """Test the set_away_mode service forwards the value to ESPHome."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
            supported_features=WaterHeaterFeature.SUPPORTS_AWAY_MODE,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            target_temperature=50.0,
            state=WaterHeaterStateFlag(0),
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_AWAY_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.test_my_boiler",
            ATTR_AWAY_MODE: away_mode,
        },
        blocking=True,
    )

    mock_client.water_heater_command.assert_has_calls(
        [call(key=1, away=away_mode, device_id=0)]
    )
