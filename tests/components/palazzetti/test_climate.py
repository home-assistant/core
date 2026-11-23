"""Tests for the Palazzetti climate platform."""

from unittest.mock import AsyncMock, patch

from pypalazzetti.exceptions import CommunicationError, ValidationError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.components.palazzetti.const import FAN_AUTO, FAN_HIGH
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "climate.stove"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.palazzetti.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_async_set_data(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting climate data via service call."""
    await setup_integration(hass, mock_config_entry)

    # Set HVAC Mode: Success
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    mock_palazzetti_client.set_on.assert_called_once_with(True)
    mock_palazzetti_client.set_on.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    mock_palazzetti_client.set_on.assert_called_once_with(False)
    mock_palazzetti_client.set_on.reset_mock()

    # Set HVAC Mode: Error
    mock_palazzetti_client.set_on.side_effect = CommunicationError()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

    mock_palazzetti_client.set_on.side_effect = ValidationError()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

    # Set Temperature: Success
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.TEMPERATURE: 22},
        blocking=True,
    )
    mock_palazzetti_client.set_target_temperature.assert_called_once_with(22)
    mock_palazzetti_client.set_target_temperature.reset_mock()

    # Set Temperature: Error
    mock_palazzetti_client.set_target_temperature.side_effect = CommunicationError()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.TEMPERATURE: 22},
            blocking=True,
        )

    mock_palazzetti_client.set_target_temperature.side_effect = ValidationError()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.TEMPERATURE: 22},
            blocking=True,
        )

    # Set Fan Mode: Success
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.FAN_MODE: FAN_HIGH},
        blocking=True,
    )
    mock_palazzetti_client.set_fan_high.assert_called_once()
    mock_palazzetti_client.set_fan_high.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.FAN_MODE: FAN_AUTO},
        blocking=True,
    )
    mock_palazzetti_client.set_fan_auto.assert_called_once()
    mock_palazzetti_client.set_fan_auto.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.FAN_MODE: "3"},
        blocking=True,
    )
    mock_palazzetti_client.set_fan_speed.assert_called_once_with(3)
    mock_palazzetti_client.set_fan_speed.reset_mock()

    # Set Fan Mode: Error
    mock_palazzetti_client.set_fan_speed.side_effect = CommunicationError()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_FAN_MODE,
            {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.FAN_MODE: 3},
            blocking=True,
        )

    mock_palazzetti_client.set_fan_speed.side_effect = ValidationError()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_FAN_MODE,
            {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.FAN_MODE: 3},
            blocking=True,
        )
