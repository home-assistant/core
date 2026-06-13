"""Tests for the Samsung Infrared climate platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    FAN_HIGH,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.samsung_infrared.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
        assert sent_command.payload[19] == 0x11

        mock_send_command.reset_mock()

        await hass.services.async_call(
            "climate",
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 26},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.payload[18] == (26 - 16) << 4

        mock_send_command.reset_mock()

        await hass.services.async_call(
            "climate",
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.payload[19] == 0x11 | (5 << 1)
