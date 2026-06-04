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
    # 1. Create a fake state for the infrared emitter so the climate entity becomes available
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

    # Patch the entity's internal _send_command method to verify the library input
    with patch(
        "homeassistant.components.samsung_infrared.climate.SamsungIrClimate._send_command",
        new_callable=AsyncMock,
    ) as mock_send_command:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "climate.samsung_ac"

        # Verify the entity is actually available now
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"

        # 2. Test HVAC mode change (e.g., setting to COOL)
        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        mock_send_command.assert_called_once()

        # Verify that the object passed to _send_command has the correct parameters
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.payload[6] == 0x01

        mock_send_command.reset_mock()

        # 3. Test temperature change (e.g., setting to 26°C)
        await hass.services.async_call(
            "climate",
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 26},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.payload[5] == (26 - 16) << 4

        mock_send_command.reset_mock()

        # 4. Test fan mode change (e.g., setting to HIGH)
        await hass.services.async_call(
            "climate",
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        sent_command = mock_send_command.call_args[0][0]
        assert sent_command.payload[7] == 0xA0
