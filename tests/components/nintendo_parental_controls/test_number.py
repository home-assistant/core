"""Test number platform for Nintendo Parental Controls."""

from unittest.mock import AsyncMock, patch

from pynintendoparental.exceptions import DailyPlaytimeOutOfRangeError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test number platform."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.NUMBER],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test number platform service."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.NUMBER],
    ):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: "120"},
        target={ATTR_ENTITY_ID: "number.home_assistant_test_max_screentime_today"},
        blocking=True,
    )
    assert len(mock_nintendo_device.update_max_daily_playtime.mock_calls) == 1


async def test_set_number_service_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test number platform service validation errors."""
    mock_nintendo_device.update_max_daily_playtime.side_effect = (
        DailyPlaytimeOutOfRangeError(None)
    )
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.NUMBER],
    ):
        await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: "361"},
            target={ATTR_ENTITY_ID: "number.home_assistant_test_max_screentime_today"},
            blocking=True,
        )
    assert len(mock_nintendo_device.update_max_daily_playtime.mock_calls) == 1
    assert err.value.translation_key == "daily_playtime_out_of_range"
