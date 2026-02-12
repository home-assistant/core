"""Tests for the Actron Air climate platform."""

from unittest.mock import MagicMock, patch

from actron_neo_api import ActronAirAPIError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_climate_entities(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_zone: MagicMock,
) -> None:
    """Test climate entities."""
    status = mock_actron_api.state_manager.get_status.return_value
    status.remote_zone_info = [mock_zone]
    status.zones = {1: mock_zone}

    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_system_set_temperature(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature for system climate entity."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_system", ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    status.user_aircon_settings.set_temperature.assert_awaited_once_with(
        temperature=22.5
    )


async def test_system_set_temperature_api_error(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test API error when setting temperature for system climate entity."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value
    status.user_aircon_settings.set_temperature.side_effect = ActronAirAPIError(
        "Test error"
    )

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.test_system", ATTR_TEMPERATURE: 22.5},
            blocking=True,
        )


async def test_system_set_fan_mode(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting fan mode for system climate entity."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.test_system", ATTR_FAN_MODE: "low"},
        blocking=True,
    )

    status.user_aircon_settings.set_fan_mode.assert_awaited_once_with("LOW")


async def test_system_set_fan_mode_api_error(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test API error when setting fan mode for system climate entity."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value
    status.user_aircon_settings.set_fan_mode.side_effect = ActronAirAPIError(
        "Test error"
    )

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.test_system", ATTR_FAN_MODE: "high"},
            blocking=True,
        )


async def test_system_set_hvac_mode(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode for system climate entity."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.test_system", ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    status.ac_system.set_system_mode.assert_awaited_once_with("COOL")


async def test_system_set_hvac_mode_api_error(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test API error when setting HVAC mode for system climate entity."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value
    status.ac_system.set_system_mode.side_effect = ActronAirAPIError("Test error")

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.test_system", ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )


async def test_zone_set_temperature(
    hass: HomeAssistant,
    init_integration_with_zone: None,
    mock_zone: MagicMock,
) -> None:
    """Test setting temperature for zone climate entity."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )

    mock_zone.set_temperature.assert_awaited_once_with(temperature=23.0)


async def test_zone_set_temperature_api_error(
    hass: HomeAssistant,
    init_integration_with_zone: None,
    mock_zone: MagicMock,
) -> None:
    """Test API error when setting temperature for zone climate entity."""
    mock_zone.set_temperature.side_effect = ActronAirAPIError("Test error")

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: 23.0},
            blocking=True,
        )


async def test_zone_set_hvac_mode_on(
    hass: HomeAssistant,
    init_integration_with_zone: None,
    mock_zone: MagicMock,
) -> None:
    """Test setting HVAC mode to on for zone climate entity."""
    mock_zone.is_active = False
    mock_zone.hvac_mode = "OFF"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    mock_zone.enable.assert_awaited_once_with(True)


async def test_zone_set_hvac_mode_off(
    hass: HomeAssistant,
    init_integration_with_zone: None,
    mock_zone: MagicMock,
) -> None:
    """Test setting HVAC mode to off for zone climate entity."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    mock_zone.enable.assert_awaited_once_with(False)


async def test_zone_set_hvac_mode_api_error(
    hass: HomeAssistant,
    init_integration_with_zone: None,
    mock_zone: MagicMock,
) -> None:
    """Test API error when setting HVAC mode for zone climate entity."""
    mock_zone.enable.side_effect = ActronAirAPIError("Test error")

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )
