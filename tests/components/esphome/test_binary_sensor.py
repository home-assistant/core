"""Test ESPHome binary sensors."""
from unittest.mock import AsyncMock, Mock

from aioesphomeapi import DeviceInfo

from homeassistant.components.esphome import DOMAIN, DomainData
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_call_active(
    hass: HomeAssistant,
    mock_client,
) -> None:
    """Test call active binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    device_info = DeviceInfo(
        name="test",
        friendly_name="Test",
        voice_assistant_version=1,
        mac_address="11:22:33:44:55:aa",
        esphome_version="1.0.0",
    )

    mock_client.device_info = AsyncMock(return_value=device_info)
    mock_client.subscribe_voice_assistant = AsyncMock(return_value=Mock())

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    entry_data = DomainData.get(hass).get_entry_data(entry)

    state = hass.states.get("binary_sensor.test_call_active")
    assert state is not None
    assert state.state == "off"

    entry_data.async_set_assist_pipeline_state(True)

    state = hass.states.get("binary_sensor.test_call_active")
    assert state.state == "on"

    entry_data.async_set_assist_pipeline_state(False)

    state = hass.states.get("binary_sensor.test_call_active")
    assert state.state == "off"
