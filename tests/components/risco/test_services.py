"""Tests for the Risco services."""

from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.risco import DOMAIN
from homeassistant.components.risco.const import SERVICE_SET_TIME
from homeassistant.core import HomeAssistant


async def test_set_time_service(
    hass: HomeAssistant, setup_risco_local, local_config_entry
) -> None:
    """Test the set_time service."""
    with patch("homeassistant.components.risco.RiscoLocal.set_time") as mock:
        time_str = "2025-02-21T12:00:00"
        time = datetime.fromisoformat(time_str)
        data = {
            "config_entry_id": local_config_entry.entry_id,
            "time": time_str,
        }

        await hass.services.async_call(
            DOMAIN, SERVICE_SET_TIME, service_data=data, blocking=True
        )

        mock.assert_called_once_with(time)


@pytest.mark.freeze_time("2025-02-21T12:00:00Z")
async def test_set_time_service_with_no_time(
    hass: HomeAssistant, setup_risco_local, local_config_entry
) -> None:
    """Test the set_time service when no time is provided."""
    with patch("homeassistant.components.risco.RiscoLocal.set_time") as mock_set_time:
        data = {
            "config_entry_id": local_config_entry.entry_id,
        }

        await hass.services.async_call(
            DOMAIN, SERVICE_SET_TIME, service_data=data, blocking=True
        )

        mock_set_time.assert_called_once_with(datetime.now())
