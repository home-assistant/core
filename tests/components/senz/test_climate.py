"""Test Senz climate platform."""

from unittest.mock import MagicMock, patch

from httpx import RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

TEST_DOMAIN = CLIMATE_DOMAIN
TEST_ENTITY_ID = "climate.test_room_1"
SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_HVAC_MODE = "set_hvac_mode"


async def test_climate_snapshot(
    hass: HomeAssistant,
    mock_senz_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate setup for cloud connection."""
    with patch("homeassistant.components.senz.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_set_target(
    hass: HomeAssistant,
    mock_senz_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting of target temperature."""

    with (
        patch("homeassistant.components.senz.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.senz.Thermostat.manual", return_value=None
        ) as mock_manual,
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.services.async_call(
            TEST_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_TEMPERATURE: 17},
            blocking=True,
        )
    mock_manual.assert_called_once_with(17.0)


async def test_set_target_fail(
    hass: HomeAssistant,
    mock_senz_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that failed set_temperature is handled."""

    with (
        patch("homeassistant.components.senz.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.senz.Thermostat.manual",
            side_effect=RequestError("API error"),
        ) as mock_manual,
    ):
        await setup_integration(hass, mock_config_entry)
        with pytest.raises(
            HomeAssistantError, match="Failed to set target temperature on the device"
        ):
            await hass.services.async_call(
                TEST_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_TEMPERATURE: 17},
                blocking=True,
            )
    mock_manual.assert_called_once()


@pytest.mark.parametrize(
    ("mode", "manual_count", "auto_count"),
    [(HVACMode.HEAT, 1, 0), (HVACMode.AUTO, 0, 1)],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_senz_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mode: str,
    manual_count: int,
    auto_count: int,
) -> None:
    """Test setting of hvac mode."""

    with (
        patch("homeassistant.components.senz.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.senz.Thermostat.manual", return_value=None
        ) as mock_manual,
        patch(
            "homeassistant.components.senz.Thermostat.auto", return_value=None
        ) as mock_auto,
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.services.async_call(
            TEST_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_HVAC_MODE: mode},
            blocking=True,
        )
    assert mock_manual.call_count == manual_count
    assert mock_auto.call_count == auto_count


async def test_set_hvac_mode_fail(
    hass: HomeAssistant,
    mock_senz_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that failed set_hvac_mode is handled."""

    with (
        patch("homeassistant.components.senz.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.senz.Thermostat.manual",
            side_effect=RequestError("API error"),
        ) as mock_manual,
    ):
        await setup_integration(hass, mock_config_entry)
        with pytest.raises(
            HomeAssistantError, match="Failed to set hvac mode on the device"
        ):
            await hass.services.async_call(
                TEST_DOMAIN,
                SERVICE_SET_HVAC_MODE,
                {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
                blocking=True,
            )
    mock_manual.assert_called_once()
