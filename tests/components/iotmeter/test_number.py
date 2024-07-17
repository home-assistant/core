"""Test module for IoTMeter number entities in Home Assistant."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.iotmeter.const import DOMAIN
from homeassistant.components.iotmeter.number import (
    ChargingCurrentNumber,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant


async def test_charging_current_number(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test charging current number entity."""
    mock_coordinator = AsyncMock()
    mock_coordinator.data = {
        "EVSE_CURRENT": 10,
    }
    mock_coordinator.ip_address = "192.168.1.1"
    mock_coordinator.port = 8000
    mock_coordinator.async_request_refresh = AsyncMock(return_value=None)
    hass.data[DOMAIN] = {"coordinator": mock_coordinator}

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="iotmeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source="test",
        options={},
        entry_id="1",
        unique_id="unique_id_123",
    )

    await async_setup_entry(hass, config_entry, lambda entities: None)
    await hass.async_block_till_done()

    number_entity = ChargingCurrentNumber(
        coordinator=mock_coordinator,
        sensor_type="Charging Current",
        translations={},
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        min_value=0,
        max_value=32,
        step=1,
    )
    number_entity.hass = hass  # Set the Home Assistant instance
    assert number_entity.state == 10
    assert number_entity.device_info["manufacturer"] == "Vilmio"
    assert number_entity.device_info["model"] == "IoTMeter"
    assert number_entity.icon == "mdi:power-plug"

    with patch("homeassistant.components.iotmeter.number.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        await number_entity.async_set_native_value(20)
        await hass.async_block_till_done()  # Wait for all tasks to be done

        mock_coordinator.data["EVSE_CURRENT"] = 20
        await mock_coordinator.async_request_refresh()
        await hass.async_block_till_done()

        assert number_entity.state == 20  # Check updated state
        mock_post.assert_called_once_with(
            url="http://192.168.1.1:8000/updateRamSetting",
            json={"variable": "EVSE_CURRENT", "value": 20},
            timeout=5,
        )

        # Ensure that the coordinator's data is updated to reflect the new state
    mock_coordinator.data["EVSE_CURRENT"] = 20
    await number_entity.coordinator.async_request_refresh()
    await hass.async_block_till_done()
    assert number_entity.state == 20
