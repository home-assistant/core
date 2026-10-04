"""Tests for the Besen services."""

from datetime import UTC, datetime
from unittest.mock import Mock

from besen.exceptions import CommandFailed
import probatio
import pytest

from homeassistant.components.besen.const import DOMAIN
from homeassistant.components.besen.services import BesenService, BesenServiceArgument
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import setup_integration

from tests.common import MockConfigEntry

ENTITY_ID = "switch.garage_charge"
START = "2026-10-01T22:00:00+00:00"
START_UTC = datetime(2026, 10, 1, 22, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("service_data", "start", "duration_minutes"),
    [
        pytest.param({}, None, None, id="now"),
        pytest.param(
            {BesenServiceArgument.START: START}, START_UTC, None, id="scheduled"
        ),
        # A time without an offset is in the Home Assistant time zone.
        pytest.param(
            {BesenServiceArgument.START: "2026-10-01 15:00:00"},
            START_UTC,
            None,
            id="local_time",
        ),
        pytest.param(
            {BesenServiceArgument.DURATION: {"hours": 1, "minutes": 30}},
            None,
            90,
            id="time_limited",
        ),
        pytest.param(
            {
                BesenServiceArgument.START: START,
                BesenServiceArgument.DURATION: {"minutes": 45},
            },
            START_UTC,
            45,
            id="scheduled_and_time_limited",
        ),
    ],
)
async def test_start_charging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    service_data: dict[str, str | dict[str, int]],
    start: datetime | None,
    duration_minutes: int | None,
) -> None:
    """Test the start charging action passes the schedule to the charger."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    await hass.services.async_call(
        DOMAIN,
        BesenService.START_CHARGING,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_besen_client.async_start_charging.assert_awaited_once_with(
        start=start, duration_minutes=duration_minutes
    )


@pytest.mark.parametrize(
    "duration",
    [
        pytest.param({"seconds": 59}, id="too_short"),
        pytest.param({"minutes": 65535}, id="too_long"),
        pytest.param({"minutes": 1, "seconds": 30}, id="not_whole_minutes"),
    ],
)
async def test_start_charging_invalid_duration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    duration: dict[str, int],
) -> None:
    """Test a duration the charger cannot store is rejected."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            BesenService.START_CHARGING,
            {ATTR_ENTITY_ID: ENTITY_ID, BesenServiceArgument.DURATION: duration},
            blocking=True,
        )

    mock_besen_client.async_start_charging.assert_not_awaited()


@pytest.mark.parametrize(
    ("side_effect", "exception", "translation_key"),
    [
        pytest.param(
            ValueError("in the past"),
            ServiceValidationError,
            "invalid_start",
            id="invalid_start",
        ),
        pytest.param(
            CommandFailed("rejected"),
            HomeAssistantError,
            "command_failed",
            id="charger_rejection",
        ),
    ],
)
async def test_start_charging_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    side_effect: Exception,
    exception: type[HomeAssistantError],
    translation_key: str,
) -> None:
    """Test an unusable start time and a charger rejection are reported."""

    mock_besen_client.async_start_charging.side_effect = side_effect

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    with pytest.raises(exception) as err:
        await hass.services.async_call(
            DOMAIN,
            BesenService.START_CHARGING,
            {ATTR_ENTITY_ID: ENTITY_ID, BesenServiceArgument.START: START},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
