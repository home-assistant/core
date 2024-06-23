"""Tests for the AirGradient select platform."""

from unittest.mock import AsyncMock, patch

from airgradient import ConfigurationControl
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    airgradient_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_setting_value(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.airgradient_configuration_source",
            ATTR_OPTION: "local",
        },
        blocking=True,
    )
    mock_airgradient_client.set_configuration_control.assert_called_once_with("local")
    assert mock_airgradient_client.get_config.call_count == 2


async def test_setting_protected_value(
    hass: HomeAssistant,
    mock_cloud_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting protected value."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.airgradient_display_temperature_unit",
                ATTR_OPTION: "c",
            },
            blocking=True,
        )
    mock_cloud_airgradient_client.set_temperature_unit.assert_not_called()

    mock_cloud_airgradient_client.get_config.return_value.configuration_control = (
        ConfigurationControl.LOCAL
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.airgradient_display_temperature_unit",
            ATTR_OPTION: "c",
        },
        blocking=True,
    )
    mock_cloud_airgradient_client.set_temperature_unit.assert_called_once_with("c")
