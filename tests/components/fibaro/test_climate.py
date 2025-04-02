"""Test the Fibaro climate platform."""

from unittest.mock import Mock, patch

from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry


async def test_climate_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat: Mock,
    mock_room: Mock,
) -> None:
    """Test that the climate creates an entity."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_thermostat]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        entry = entity_registry.async_get("climate.room_1_test_climate_4")
        assert entry
        assert entry.unique_id == "hc2_111111.4"
        assert entry.original_name == "Room 1 Test climate"
        assert entry.supported_features == (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE
        )


async def test_hvac_mode_preset(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat: Mock,
    mock_room: Mock,
) -> None:
    """Test that the climate state is auto when a preset is selected."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_thermostat]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        state = hass.states.get("climate.room_1_test_climate_4")
        assert state.state == HVACMode.AUTO
        assert state.attributes["preset_mode"] == "CustomerSpecific"


async def test_hvac_mode_heat(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat: Mock,
    mock_room: Mock,
) -> None:
    """Test that the preset mode is None if a hvac mode is active."""

    # Arrange
    mock_thermostat.thermostat_mode = "Heat"
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_thermostat]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        state = hass.states.get("climate.room_1_test_climate_4")
        assert state.state == HVACMode.HEAT
        assert state.attributes["preset_mode"] is None


async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat: Mock,
    mock_room: Mock,
) -> None:
    """Test that set_hvac_mode() works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_thermostat]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": "climate.room_1_test_climate_4", "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )

        # Assert
        mock_thermostat.execute_action.assert_called_once()


async def test_hvac_mode_with_operation_mode_support(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_with_operating_mode: Mock,
    mock_room: Mock,
) -> None:
    """Test that operating mode works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_thermostat_with_operating_mode]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        state = hass.states.get("climate.room_1_test_climate_6")
        assert state.state == HVACMode.AUTO


async def test_set_hvac_mode_with_operation_mode_support(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_with_operating_mode: Mock,
    mock_room: Mock,
) -> None:
    """Test that set_hvac_mode() works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_thermostat_with_operating_mode]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": "climate.room_1_test_climate_6", "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )

        # Assert
        mock_thermostat_with_operating_mode.execute_action.assert_called_once()


async def test_fan_mode(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_parent: Mock,
    mock_thermostat_with_operating_mode: Mock,
    mock_fan_device: Mock,
    mock_room: Mock,
) -> None:
    """Test that operating mode works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [
        mock_thermostat_parent,
        mock_thermostat_with_operating_mode,
        mock_fan_device,
    ]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        state = hass.states.get("climate.room_1_test_climate_6")
        assert state.attributes["fan_mode"] == "low"
        assert state.attributes["fan_modes"] == ["off", "low", "auto_high"]


async def test_set_fan_mode(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_parent: Mock,
    mock_thermostat_with_operating_mode: Mock,
    mock_fan_device: Mock,
    mock_room: Mock,
) -> None:
    """Test that set_fan_mode() works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [
        mock_thermostat_parent,
        mock_thermostat_with_operating_mode,
        mock_fan_device,
    ]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "climate",
            "set_fan_mode",
            {"entity_id": "climate.room_1_test_climate_6", "fan_mode": "off"},
            blocking=True,
        )

        # Assert
        mock_fan_device.execute_action.assert_called_once()


async def test_target_temperature(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_parent: Mock,
    mock_thermostat_with_operating_mode: Mock,
    mock_fan_device: Mock,
    mock_room: Mock,
) -> None:
    """Test that operating mode works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [
        mock_thermostat_parent,
        mock_thermostat_with_operating_mode,
        mock_fan_device,
    ]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        state = hass.states.get("climate.room_1_test_climate_6")
        assert state.attributes["temperature"] == 23


async def test_set_target_temperature(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_thermostat_parent: Mock,
    mock_thermostat_with_operating_mode: Mock,
    mock_fan_device: Mock,
    mock_room: Mock,
) -> None:
    """Test that set_fan_mode() works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [
        mock_thermostat_parent,
        mock_thermostat_with_operating_mode,
        mock_fan_device,
    ]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.CLIMATE]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.room_1_test_climate_6", "temperature": 25.5},
            blocking=True,
        )

        # Assert
        mock_thermostat_with_operating_mode.execute_action.assert_called_once()
