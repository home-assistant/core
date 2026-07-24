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


@pytest.mark.parametrize(
    ("entity_id", "new_value", "called_function_name"),
    [
        ("time.home_assistant_test_bedtime_alarm", "20:00:00", "set_bedtime_alarm"),
        (
            "time.home_assistant_test_bedtime_end_time",
            "06:30:00",
            "set_bedtime_end_time",
        ),
    ],
)
async def test_set_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    entity_id: str,
    new_value: str,
    called_function_name: str,
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
        service_data={ATTR_TIME: new_value},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(getattr(mock_nintendo_device, called_function_name).mock_calls) == 1


@pytest.mark.parametrize(
    ("entity_id", "new_value", "translation_key", "called_function_name"),
    [
        (
            "time.home_assistant_test_bedtime_alarm",
            "03:00:00",
            "bedtime_alarm_out_of_range",
            "set_bedtime_alarm",
        ),
        (
            "time.home_assistant_test_bedtime_end_time",
            "10:00:00",
            "bedtime_end_time_out_of_range",
            "set_bedtime_end_time",
        ),
    ],
)
async def test_set_time_service_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    entity_id: str,
    new_value: str,
    translation_key: str,
    called_function_name: str,
) -> None:
    """Test time platform service validation errors."""
    getattr(
        mock_nintendo_device, called_function_name
    ).side_effect = BedtimeOutOfRangeError(None)
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.TIME],
    ):
        await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={ATTR_TIME: new_value},
            target={ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert len(getattr(mock_nintendo_device, called_function_name).mock_calls) == 1
    assert err.value.translation_key == translation_key
