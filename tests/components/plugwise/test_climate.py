"""Tests for the Plugwise Climate integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from plugwise.exceptions import PlugwiseError
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_HOME,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry, async_fire_time_changed

HA_PLUGWISE_SMILE_ASYNC_UPDATE = (
    "homeassistant.components.plugwise.coordinator.Smile.async_update"
)


async def test_adam_climate_entity_attributes(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of adam climate device environment."""
    state = hass.states.get("climate.woonkamer")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.AUTO, HVACMode.HEAT]
    assert ATTR_PRESET_MODES in state.attributes
    assert "no_frost" in state.attributes[ATTR_PRESET_MODES]
    assert PRESET_HOME in state.attributes[ATTR_PRESET_MODES]
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOME
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.9
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 17
    assert state.attributes[ATTR_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_MIN_TEMP] == 0.0
    assert state.attributes[ATTR_MAX_TEMP] == 35.0
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 0.1

    state = hass.states.get("climate.jessie")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.AUTO, HVACMode.HEAT]
    assert ATTR_PRESET_MODES in state.attributes
    assert "no_frost" in state.attributes[ATTR_PRESET_MODES]
    assert PRESET_HOME in state.attributes[ATTR_PRESET_MODES]
    assert state.attributes[ATTR_PRESET_MODE] == "asleep"
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 17.2
    assert state.attributes[ATTR_TEMPERATURE] == 15.0
    assert state.attributes[ATTR_MIN_TEMP] == 0.0
    assert state.attributes[ATTR_MAX_TEMP] == 35.0
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 0.1


async def test_adam_2_climate_entity_attributes(
    hass: HomeAssistant, mock_smile_adam_2: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of adam climate device environment."""
    state = hass.states.get("climate.living_room")
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.PREHEATING
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.HEAT,
    ]

    state = hass.states.get("climate.bathroom")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.HEAT,
    ]


async def test_adam_3_climate_entity_attributes(
    hass: HomeAssistant,
    mock_smile_adam_3: MagicMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of adam climate device environment."""
    state = hass.states.get("climate.living_room")
    assert state
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
    ]
    data = mock_smile_adam_3.async_update.return_value
    data.devices["da224107914542988a88561b4452b0f6"]["select_regulation_mode"] = (
        "heating"
    )
    data.devices["f2bf9048bef64cc5b6d5110154e33c81"]["control_state"] = (
        HVACAction.HEATING
    )
    data.devices["056ee145a816487eaa69243c3280f8bf"]["binary_sensors"][
        "cooling_state"
    ] = False
    data.devices["056ee145a816487eaa69243c3280f8bf"]["binary_sensors"][
        "heating_state"
    ] = True
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get("climate.living_room")
        assert state
        assert state.state == HVACMode.HEAT
        assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
        assert state.attributes[ATTR_HVAC_MODES] == [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.HEAT,
        ]

    data = mock_smile_adam_3.async_update.return_value
    data.devices["da224107914542988a88561b4452b0f6"]["select_regulation_mode"] = (
        "cooling"
    )
    data.devices["f2bf9048bef64cc5b6d5110154e33c81"]["control_state"] = (
        HVACAction.COOLING
    )
    data.devices["056ee145a816487eaa69243c3280f8bf"]["binary_sensors"][
        "cooling_state"
    ] = True
    data.devices["056ee145a816487eaa69243c3280f8bf"]["binary_sensors"][
        "heating_state"
    ] = False
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get("climate.living_room")
        assert state
        assert state.state == HVACMode.COOL
        assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
        assert state.attributes[ATTR_HVAC_MODES] == [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.COOL,
        ]


async def test_adam_climate_adjust_negative_testing(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test PlugwiseError exception."""
    mock_smile_adam.set_temperature.side_effect = PlugwiseError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.woonkamer", ATTR_TEMPERATURE: 25},
            blocking=True,
        )


async def test_adam_climate_entity_climate_changes(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test handling of user requests in adam climate device environment."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.woonkamer", ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert mock_smile_adam.set_temperature.call_count == 1
    mock_smile_adam.set_temperature.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", {"setpoint": 25.0}
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.woonkamer",
            ATTR_HVAC_MODE: HVACMode.HEAT,
            ATTR_TEMPERATURE: 25,
        },
        blocking=True,
    )
    assert mock_smile_adam.set_temperature.call_count == 2
    mock_smile_adam.set_temperature.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", {"setpoint": 25.0}
    )

    with pytest.raises(ServiceValidationError, match="Accepted range"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.woonkamer", ATTR_TEMPERATURE: 150},
            blocking=True,
        )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.woonkamer", ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    assert mock_smile_adam.set_preset.call_count == 1
    mock_smile_adam.set_preset.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", PRESET_AWAY
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.woonkamer", ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    assert mock_smile_adam.set_schedule_state.call_count == 2
    mock_smile_adam.set_schedule_state.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e", HVACMode.OFF
    )

    with pytest.raises(ServiceValidationError, match="valid modes are"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.jessie",
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )


async def test_adam_climate_off_mode_change(
    hass: HomeAssistant,
    mock_smile_adam_4: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test handling of user requests in adam climate device environment."""
    state = hass.states.get("climate.slaapkamer")
    assert state
    assert state.state == HVACMode.OFF
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.slaapkamer",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    assert mock_smile_adam_4.set_schedule_state.call_count == 1
    assert mock_smile_adam_4.set_regulation_mode.call_count == 1
    mock_smile_adam_4.set_regulation_mode.assert_called_with("heating")

    state = hass.states.get("climate.kinderkamer")
    assert state
    assert state.state == HVACMode.HEAT
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.kinderkamer",
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    assert mock_smile_adam_4.set_schedule_state.call_count == 1
    assert mock_smile_adam_4.set_regulation_mode.call_count == 2
    mock_smile_adam_4.set_regulation_mode.assert_called_with("off")

    state = hass.states.get("climate.logeerkamer")
    assert state
    assert state.state == HVACMode.HEAT
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.logeerkamer",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    assert mock_smile_adam_4.set_schedule_state.call_count == 1
    assert mock_smile_adam_4.set_regulation_mode.call_count == 2


async def test_anna_climate_entity_attributes(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of anna climate device environment."""
    state = hass.states.get("climate.anna")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.AUTO, HVACMode.HEAT_COOL]

    assert "no_frost" in state.attributes[ATTR_PRESET_MODES]
    assert PRESET_HOME in state.attributes[ATTR_PRESET_MODES]

    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19.3
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOME
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 18
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 30
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 20.5
    assert state.attributes[ATTR_MIN_TEMP] == 4
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 0.1


async def test_anna_2_climate_entity_attributes(
    hass: HomeAssistant,
    mock_smile_anna_2: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of anna climate device environment."""
    state = hass.states.get("climate.anna")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.AUTO,
        HVACMode.HEAT_COOL,
    ]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 18
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 30
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 20.5


async def test_anna_3_climate_entity_attributes(
    hass: HomeAssistant,
    mock_smile_anna_3: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of anna climate device environment."""
    state = hass.states.get("climate.anna")
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.AUTO,
        HVACMode.HEAT_COOL,
    ]


async def test_anna_climate_entity_climate_changes(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handling of user requests in anna climate device environment."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.anna",
            ATTR_TARGET_TEMP_HIGH: 30,
            ATTR_TARGET_TEMP_LOW: 20,
        },
        blocking=True,
    )
    assert mock_smile_anna.set_temperature.call_count == 1
    mock_smile_anna.set_temperature.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5",
        {"setpoint_high": 30.0, "setpoint_low": 20.0},
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.anna", ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    assert mock_smile_anna.set_preset.call_count == 1
    mock_smile_anna.set_preset.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5", PRESET_AWAY
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.anna", ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    # hvac_mode is already auto so not called.
    assert mock_smile_anna.set_schedule_state.call_count == 0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.anna", ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    assert mock_smile_anna.set_schedule_state.call_count == 1
    mock_smile_anna.set_schedule_state.assert_called_with(
        "c784ee9fdab44e1395b8dee7d7a497d5", HVACMode.OFF
    )

    data = mock_smile_anna.async_update.return_value
    data.devices["3cb70739631c4d17a86b8b12e8a5161b"].pop("available_schedules")
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get("climate.anna")
        assert state.state == HVACMode.HEAT
        assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.HEAT_COOL]
