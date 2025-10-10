"""Test the time platform."""

from unittest.mock import AsyncMock, patch

from pynintendoparental.exceptions import BedtimeOutOfRangeError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test time platform."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.TIME],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test time platform service validation errors."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.TIME],
    ):
        await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_TIME: "20:00:00"},
        target={ATTR_ENTITY_ID: "time.home_assistant_test_bedtime_alarm"},
        blocking=True,
    )
    assert len(mock_nintendo_device.set_bedtime_alarm.mock_calls) == 1


async def test_set_time_service_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test time platform service validation errors."""
    mock_nintendo_device.set_bedtime_alarm.side_effect = BedtimeOutOfRangeError(None)
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.TIME],
    ):
        await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={ATTR_TIME: "01:00:00"},
            target={ATTR_ENTITY_ID: "time.home_assistant_test_bedtime_alarm"},
            blocking=True,
        )
    assert len(mock_nintendo_device.set_bedtime_alarm.mock_calls) == 1
    assert err.value.translation_key == "bedtime_alarm_out_of_range"
