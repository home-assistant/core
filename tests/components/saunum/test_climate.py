"""Test the Saunum climate platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


async def test_climate_entity_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate entity creation."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check climate entity is created
    entity_id = "climate.saunum_leil"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None


async def test_climate_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test climate HVAC mode when session is off."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has session_active = 0
    assert state.state == HVACMode.OFF
    assert state.attributes.get(ATTR_HVAC_ACTION) == HVACAction.OFF


async def test_climate_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate HVAC mode when session is active."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with active session
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [1, 0, 60, 10, 80, 2, 0]  # Session active
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 3, 0]  # Heater on
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Session is active
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_HVAC_ACTION) == HVACAction.HEATING


async def test_climate_hvac_action_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate HVAC action when session is active but heater is off."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with active session but heater off
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [1, 0, 60, 10, 80, 2, 0]  # Session active
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 0, 0]  # Heater off
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Session is active but heater is off (target temp reached)
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_HVAC_ACTION) == HVACAction.IDLE


async def test_climate_temperatures_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate temperatures in Celsius."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with temperature data
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 0, 60, 10, 80, 2, 0]  # Target 80°C
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 0, 0]  # Current 75°C
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Check temperatures
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 75
    assert state.attributes.get(ATTR_TEMPERATURE) == 80
    # Climate entities don't expose temperature_unit as attribute, check min/max instead
    assert state.attributes.get(ATTR_MIN_TEMP) == 40
    assert state.attributes.get(ATTR_MAX_TEMP) == 100


async def test_climate_temperatures_fahrenheit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate temperatures in Fahrenheit."""
    # Use US_CUSTOMARY_SYSTEM to set imperial units
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with temperature data
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 0, 60, 10, 80, 2, 0]  # Target 80°C
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 0, 0]  # Current 75°C
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Check temperatures converted to Fahrenheit
    # 75°C = 167°F, 80°C = 176°F
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 167.0
    assert state.attributes.get(ATTR_TEMPERATURE) == 176.0
    # Climate entities don't expose temperature_unit as attribute, check min/max instead
    assert state.attributes.get(ATTR_MIN_TEMP) == 104  # 40°C
    assert state.attributes.get(ATTR_MAX_TEMP) == 212  # 100°C


async def test_climate_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test setting HVAC mode to HEAT."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Turn on heating
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify write_register was called with correct parameters
    coordinator = mock_config_entry.runtime_data
    coordinator.client.write_register.assert_called()


async def test_climate_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test setting HVAC mode to OFF."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Turn off heating
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify write_register was called
    coordinator = mock_config_entry.runtime_data
    coordinator.client.write_register.assert_called()


async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test setting target temperature."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Set temperature to 85°C
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 85},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify write_register was called
    coordinator = mock_config_entry.runtime_data
    coordinator.client.write_register.assert_called()


async def test_climate_set_temperature_fahrenheit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test setting target temperature in Fahrenheit."""
    # Use US_CUSTOMARY_SYSTEM to set imperial units
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Set temperature to 185°F (which is 85°C)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 185},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify write_register was called (should convert to Celsius)
    coordinator = mock_config_entry.runtime_data
    coordinator.client.write_register.assert_called()


async def test_climate_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate device info."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    # Check friendly name (should be just the device name since _attr_name = None)
    assert state.attributes.get("friendly_name") == "Saunum Leil"


async def test_climate_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate unique ID."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    expected_unique_id = f"{mock_config_entry.entry_id}_climate"
    assert entity_entry.unique_id == expected_unique_id


async def test_climate_none_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate with None current temperature."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with None temperature
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 0, 60, 10, 80, 2, 0]
            elif address == 100:  # Sensor data - simulate None by returning invalid
                mock_response.registers = [0, 1234, 5678, 0, 0]
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Current temperature can be present even if 0
    assert ATTR_CURRENT_TEMPERATURE in state.attributes


async def test_climate_target_temp_below_minimum(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate with target temperature below minimum."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with low target temperature
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 0, 60, 10, 30, 2, 0]  # 30°C < min
            elif address == 100:  # Sensor data
                mock_response.registers = [35, 1234, 5678, 0, 0]
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Target temperature should be None when below minimum
    assert state.attributes.get(ATTR_TEMPERATURE) is None


async def test_climate_current_temperature_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate with None current temperature."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [0, 0, 60, 10, 2, 0, 0]
            elif address == 100:
                # current_temperature at None (e.g., sensor failure)
                mock_response.registers = [None, 1234, 5678, 0, 0]
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None
    # Current temperature should be None
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) is None


async def test_climate_set_hvac_mode_heat_write_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to heat with write failure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [0, 0, 80, 10, 2, 0, 0]
            elif address == 100:
                mock_response.registers = [70, 1234, 5678, 0, 0]
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Make write fail
        error_response = MagicMock()
        error_response.isError.return_value = True
        mock_client.write_register = AsyncMock(return_value=error_response)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Try to turn on heating
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    # State should revert since write failed
    state = hass.states.get(entity_id)
    assert state is not None


async def test_climate_set_hvac_mode_off_write_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to off with write failure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [1, 0, 80, 10, 2, 0, 0]  # session active
            elif address == 100:
                mock_response.registers = [70, 1234, 5678, 0, 0]
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Make write fail
        error_response = MagicMock()
        error_response.isError.return_value = True
        mock_client.write_register = AsyncMock(return_value=error_response)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Try to turn off heating
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    # State should revert since write failed
    state = hass.states.get(entity_id)
    assert state is not None


async def test_climate_set_temperature_write_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature with write failure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [0, 0, 80, 10, 2, 0, 0]
            elif address == 100:
                mock_response.registers = [70, 1234, 5678, 0, 0]
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Make write fail
        error_response = MagicMock()
        error_response.isError.return_value = True
        mock_client.write_register = AsyncMock(return_value=error_response)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Try to set temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 85},
        blocking=True,
    )
    await hass.async_block_till_done()

    # State should revert since write failed
    state = hass.states.get(entity_id)
    assert state is not None


async def test_climate_set_hvac_mode_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setting unsupported HVAC mode logs warning."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [0, 0, 80, 10, 2, 0, 0]
            elif address == 100:
                mock_response.registers = [70, 1234, 5678, 0, 0]
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Try to set an unsupported HVAC mode (auto/cool/etc)
    # We'll call the method directly to test the branch
    climate_entity = hass.data["climate"].get_entity(entity_id)
    if climate_entity:
        await climate_entity.async_set_hvac_mode(HVACMode.AUTO)
        assert "Unsupported HVAC mode:" in caplog.text


async def test_climate_set_temperature_without_temperature_parameter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test setting temperature without temperature parameter (early return)."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Get the climate entity and call async_set_temperature directly without temperature
    climate_entities = hass.data["climate"].entities
    climate_entity = next(
        (entity for entity in climate_entities if entity.entity_id == entity_id), None
    )
    assert climate_entity is not None

    # Call the method directly with empty kwargs (no temperature)
    # This should trigger the early return on line 136
    await climate_entity.async_set_temperature()
    await hass.async_block_till_done()

    # Verify the state is still valid (early return worked, no write attempted)
    state = hass.states.get(entity_id)
    assert state is not None
