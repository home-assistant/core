"""Test Wallbox Button component."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.wallbox.coordinator import InsufficientRights
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import http_403_error, http_404_error, http_429_error, setup_integration
from .const import MOCK_BUTTON_RESUME_SCHEDULE_ID

from tests.common import MockConfigEntry


async def test_wallbox_button_resume_schedule(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox: MagicMock
) -> None:
    """Test pressing the resume schedule button calls the Wallbox API once."""

    await setup_integration(hass, entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: MOCK_BUTTON_RESUME_SCHEDULE_ID},
        blocking=True,
    )

    mock_wallbox.resumeSchedule.assert_called_once()


async def test_wallbox_button_resume_schedule_error_handling(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox: MagicMock
) -> None:
    """Test button error handling for 403, 429 and other HTTP errors."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "resumeSchedule", side_effect=http_403_error),
        pytest.raises(InsufficientRights),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: MOCK_BUTTON_RESUME_SCHEDULE_ID},
            blocking=True,
        )

    with (
        patch.object(mock_wallbox, "resumeSchedule", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: MOCK_BUTTON_RESUME_SCHEDULE_ID},
            blocking=True,
        )

    with (
        patch.object(mock_wallbox, "resumeSchedule", side_effect=http_404_error),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: MOCK_BUTTON_RESUME_SCHEDULE_ID},
            blocking=True,
        )
