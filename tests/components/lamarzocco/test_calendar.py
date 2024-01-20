"""Tests for La Marzocco calendar."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from lmcloud.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.lamarzocco.calendar import (
    ATTR_DAY_OF_WEEK,
    ATTR_ENABLE,
    ATTR_TIME_OFF,
    ATTR_TIME_ON,
    SERVICE_AUTO_ON_OFF_ENABLE,
    SERVICE_AUTO_ON_OFF_TIMES,
)
from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import async_init_integration

from tests.common import MockConfigEntry


async def test_calendar_events(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the calendar."""

    test_time = datetime(2024, 1, 12, 11, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    freezer.move_to(test_time)

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"calendar.{serial_number}_auto_on_off_schedule")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: f"calendar.{serial_number}_auto_on_off_schedule",
            EVENT_START_DATETIME: test_time,
            EVENT_END_DATETIME: test_time + timedelta(days=23),
        },
        blocking=True,
        return_response=True,
    )

    assert events == snapshot


async def test_no_calendar_events_global_disable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Assert no events when global auto on/off is disabled."""

    mock_lamarzocco.current_status["global_auto"] = "Disabled"
    test_time = datetime(2024, 1, 12, 11, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    freezer.move_to(test_time)

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"calendar.{serial_number}_auto_on_off_schedule")
    assert state

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: f"calendar.{serial_number}_auto_on_off_schedule",
            EVENT_START_DATETIME: test_time,
            EVENT_END_DATETIME: test_time + timedelta(days=23),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot


# test services


async def test_service_auto_on_off_enable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco auto on/off enable service."""

    await async_init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_ENABLE,
        {
            ATTR_ENTITY_ID: f"calendar.{mock_lamarzocco.serial_number}_auto_on_off_schedule",
            ATTR_DAY_OF_WEEK: "mon",
            ATTR_ENABLE: True,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_enable.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off_enable.assert_called_once_with(
        day_of_week="mon", enable=True
    )


async def test_service_set_auto_on_off_times(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco auto on/off times service."""

    await async_init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_TIMES,
        {
            ATTR_ENTITY_ID: f"calendar.{mock_lamarzocco.serial_number}_auto_on_off_schedule",
            ATTR_ENABLE: True,
            ATTR_DAY_OF_WEEK: "tue",
            ATTR_TIME_ON: "08:30:00",
            ATTR_TIME_OFF: "17:00:00",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off.assert_called_once_with(
        day_of_week="tue",
        hour_on=8,
        minute_on=30,
        hour_off=17,
        minute_off=0,
        enable=True,
    )


async def test_service_call_error(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an exception during the service call."""

    mock_lamarzocco.set_auto_on_off_enable.side_effect = RequestNotSuccessful(
        "BadRequest"
    )

    await async_init_integration(hass, mock_config_entry)

    with pytest.raises(
        HomeAssistantError, match="Service call encountered an error: BadRequest"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_AUTO_ON_OFF_ENABLE,
            {
                ATTR_ENTITY_ID: f"calendar.{mock_lamarzocco.serial_number}_auto_on_off_schedule",
                ATTR_DAY_OF_WEEK: "mon",
                ATTR_ENABLE: True,
            },
            blocking=True,
        )
