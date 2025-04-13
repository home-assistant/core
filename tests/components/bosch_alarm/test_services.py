"""Tests for Bosch Alarm component."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.bosch_alarm.const import (
    ATTR_CONFIG_ENTRY_ID,
    DATETIME_ATTR,
    DOMAIN,
    SET_DATE_TIME_SERVICE_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.bosch_alarm.PLATFORMS", []):
        yield


async def test_set_date_time_service(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    area: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the service calls succeed if the service call is valid."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        DOMAIN,
        SET_DATE_TIME_SERVICE_NAME,
        {
            ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id],
            DATETIME_ATTR: dt_util.now(),
        },
        blocking=True,
    )


async def test_set_date_time_service_fails_bad_entity(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    area: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the service calls succeed if the service call is done for an incorrect entity."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SET_DATE_TIME_SERVICE_NAME,
            {
                ATTR_CONFIG_ENTRY_ID: ["bad-config_id"],
                DATETIME_ATTR: dt_util.now(),
            },
            blocking=True,
        )


async def test_set_date_time_service_fails_bad_params(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    area: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the service calls succeed if the service call is done with incorrect params."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SET_DATE_TIME_SERVICE_NAME,
            {
                ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id],
                DATETIME_ATTR: "",
            },
            blocking=True,
        )
