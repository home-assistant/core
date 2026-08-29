"""Tests for the Samsung Infrared climate platform."""

from unittest.mock import AsyncMock, patch

from infrared_protocols.commands.samsung_ac import (
    SamsungAC0292Command,
    SamsungAC0292HvacMode,
    SamsungACFanMode,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.samsung_infrared.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_ON
from homeassistant.core import HomeAssistant, State

from tests.common import (
    MockConfigEntry,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)


async def test_samsung_infrared_climate_services(hass: HomeAssistant) -> None:
    """Test climate services send the correct IR commands."""
    remote_entity_id = "remote.living_room_ir"
    hass.states.async_set(remote_entity_id, STATE_ON)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "infrared_emitter_entity_id": remote_entity_id,
            "device_type": "ac",
        },
        unique_id="samsung_ir_ac_test",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.samsung_infrared.climate.SamsungIrClimate._send_command",
        new_callable=AsyncMock,
    ) as mock_send_command:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "climate.samsung_ac"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"

        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        mock_send_command.assert_called_once()

        sent_command = mock_send_command.call_args[0][0]
        assert isinstance(sent_command, SamsungAC0292Command)
        assert sent_command.hvac_mode == SamsungAC0292HvacMode.COOL

        mock_send_command.reset_mock()

        await hass.services.async_call(
            "climate",
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 26},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.target_temperature == 26

        mock_send_command.reset_mock()

        await hass.services.async_call(
            "climate",
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.fan_mode == SamsungACFanMode.HIGH


async def test_samsung_infrared_climate_turn_off_sends_bare_off_command(
    hass: HomeAssistant,
) -> None:
    """Test that turning off sends OFF with no temperature, fan, or swing fields.

    SamsungAC0292Command raises if hvac_mode is OFF and any of those fields are not
    None, so this also guards against a regression that would break every turn_off.
    """
    remote_entity_id = "remote.living_room_ir"
    hass.states.async_set(remote_entity_id, STATE_ON)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "infrared_emitter_entity_id": remote_entity_id,
            "device_type": "ac",
        },
        unique_id="samsung_ir_ac_test",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.samsung_infrared.climate.SamsungIrClimate._send_command",
        new_callable=AsyncMock,
    ) as mock_send_command:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "climate.samsung_ac"

        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        mock_send_command.reset_mock()

        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )

        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert isinstance(sent_command, SamsungAC0292Command)
        assert sent_command.hvac_mode == SamsungAC0292HvacMode.OFF
        assert sent_command.target_temperature is None
        assert sent_command.fan_mode is None
        assert sent_command.swing_mode is None


async def test_samsung_infrared_climate_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
) -> None:
    """Test that set_temperature applies an included HVAC mode atomically."""
    remote_entity_id = "remote.living_room_ir"
    hass.states.async_set(remote_entity_id, STATE_ON)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "infrared_emitter_entity_id": remote_entity_id,
            "device_type": "ac",
        },
        unique_id="samsung_ir_ac_test",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.samsung_infrared.climate.SamsungIrClimate._send_command",
        new_callable=AsyncMock,
    ) as mock_send_command:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "climate.samsung_ac"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == HVACMode.OFF

        await hass.services.async_call(
            "climate",
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_HVAC_MODE: HVACMode.COOL,
                ATTR_TEMPERATURE: 26,
            },
            blocking=True,
        )

        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.hvac_mode == SamsungAC0292HvacMode.COOL
        assert sent_command.target_temperature == 26

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == HVACMode.COOL
        assert state.attributes[ATTR_TEMPERATURE] == 26

        mock_send_command.reset_mock()

        await hass.services.async_call(
            "climate",
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22.5},
            blocking=True,
        )

        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.target_temperature == 22

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes[ATTR_TEMPERATURE] == 22


async def test_samsung_infrared_climate_set_hvac_mode_auto_normalizes_fan_mode(
    hass: HomeAssistant,
) -> None:
    """Test that switching to AUTO resets the reported fan mode to FAN_AUTO.

    SamsungAC0292Command always transmits a fixed fan value in auto mode and
    reports fan_mode=None, so the assumed state must not keep showing a previously
    selected fan speed (e.g. "high") that isn't actually being sent anymore.
    """
    remote_entity_id = "remote.living_room_ir"
    hass.states.async_set(remote_entity_id, STATE_ON)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "infrared_emitter_entity_id": remote_entity_id,
            "device_type": "ac",
        },
        unique_id="samsung_ir_ac_test",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.samsung_infrared.climate.SamsungIrClimate._send_command",
        new_callable=AsyncMock,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "climate.samsung_ac"

        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        await hass.services.async_call(
            "climate",
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH

        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.AUTO},
            blocking=True,
        )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO


async def test_samsung_infrared_climate_restores_state_after_restart(
    hass: HomeAssistant,
) -> None:
    """Test that hvac_mode, temperature, and fan_mode survive a restart."""
    remote_entity_id = "remote.living_room_ir"
    hass.states.async_set(remote_entity_id, STATE_ON)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "infrared_emitter_entity_id": remote_entity_id,
            "device_type": "ac",
        },
        unique_id="samsung_ir_ac_test",
    )
    entry.add_to_hass(hass)

    mock_restore_cache(
        hass,
        [
            State(
                "climate.samsung_ac",
                HVACMode.HEAT,
                {ATTR_TEMPERATURE: 27, ATTR_FAN_MODE: FAN_HIGH},
            )
        ],
    )

    with patch(
        "homeassistant.components.samsung_infrared.climate.SamsungIrClimate._send_command",
        new_callable=AsyncMock,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.samsung_ac")
        assert state is not None
        assert state.state == HVACMode.HEAT
        assert state.attributes[ATTR_TEMPERATURE] == 27
        assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH


async def test_samsung_infrared_climate_turn_on_after_restart_resumes_last_mode(
    hass: HomeAssistant,
) -> None:
    """Test that turn_on after a restart resumes the last non-OFF mode, not COOL.

    Regression test: without restoring _last_on_hvac_mode, an AC that was last
    HEAT and got turned OFF, then restarted, would resume in COOL on turn_on
    instead of HEAT.
    """
    remote_entity_id = "remote.living_room_ir"
    hass.states.async_set(remote_entity_id, STATE_ON)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "infrared_emitter_entity_id": remote_entity_id,
            "device_type": "ac",
        },
        unique_id="samsung_ir_ac_test",
    )
    entry.add_to_hass(hass)

    # The entity's last visible state was OFF, but it had been heating before that.
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("climate.samsung_ac", HVACMode.OFF, {}),
                {"last_on_hvac_mode": HVACMode.HEAT.value},
            )
        ],
    )

    with patch(
        "homeassistant.components.samsung_infrared.climate.SamsungIrClimate._send_command",
        new_callable=AsyncMock,
    ) as mock_send_command:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "climate.samsung_ac"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == HVACMode.OFF

        await hass.services.async_call(
            "climate",
            "turn_on",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == HVACMode.HEAT

        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.hvac_mode == SamsungAC0292HvacMode.HEAT
