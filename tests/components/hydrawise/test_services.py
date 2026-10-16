"""Test Hydrawise services."""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

from aiohttp import ClientError
from pydrawise import APIError, NotAuthorizedError
from pydrawise.schema import Zone
import pytest

from homeassistant.components.hydrawise.const import (
    ATTR_DURATION,
    ATTR_UNTIL,
    DOMAIN,
    SERVICE_RESUME,
    SERVICE_START_WATERING,
    SERVICE_SUSPEND,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_start_watering(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test that the start_watering service works as intended."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_WATERING,
        {
            ATTR_ENTITY_ID: "binary_sensor.zone_one_watering",
            ATTR_DURATION: 20,
        },
        blocking=True,
    )
    mock_pydrawise.start_zone.assert_called_once_with(
        zones[0], custom_run_duration=20 * 60
    )


async def test_start_watering_no_duration(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test that the start_watering service works with no duration specified."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_WATERING,
        {ATTR_ENTITY_ID: "binary_sensor.zone_one_watering"},
        blocking=True,
    )
    mock_pydrawise.start_zone.assert_called_once_with(zones[0], custom_run_duration=0)


async def test_resume(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test that the resume service works as intended."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESUME,
        {ATTR_ENTITY_ID: "binary_sensor.zone_one_watering"},
        blocking=True,
    )
    mock_pydrawise.resume_zone.assert_called_once_with(zones[0])


async def test_suspend(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test that the suspend service works as intended."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SUSPEND,
        {
            ATTR_ENTITY_ID: "binary_sensor.zone_one_watering",
            ATTR_UNTIL: datetime(2026, 1, 1, 0, 0, 0),
        },
        blocking=True,
    )
    mock_pydrawise.suspend_zone.assert_called_once_with(
        zones[0], until=datetime(2026, 1, 1, 0, 0, 0)
    )


@pytest.mark.parametrize(
    ("service", "service_data", "api_method"),
    [
        (SERVICE_START_WATERING, {}, "start_zone"),
        (SERVICE_SUSPEND, {ATTR_UNTIL: datetime(2026, 1, 1, 0, 0, 0)}, "suspend_zone"),
        (SERVICE_RESUME, {}, "resume_zone"),
    ],
)
@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        (APIError("Boom"), "command_error"),
        (ClientError("Boom"), "command_error"),
        (TimeoutError, "command_error"),
        (NotAuthorizedError("HTTP 401"), "invalid_auth"),
    ],
)
@pytest.mark.usefixtures("mock_added_config_entry")
async def test_service_api_error(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    service: str,
    service_data: dict[str, Any],
    api_method: str,
    side_effect: Exception,
    translation_key: str,
) -> None:
    """Test that API errors in the services raise a translated error."""
    getattr(mock_pydrawise, api_method).side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: "binary_sensor.zone_one_watering", **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
