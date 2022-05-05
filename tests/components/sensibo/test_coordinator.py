"""The test for the sensibo coordinator."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.exceptions import AuthenticationError, SensiboError
from pysensibo.model import SensiboData
import pytest

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.components.sensibo.coordinator import SensiboDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_coordinator(hass: HomeAssistant, load_int: ConfigEntry) -> None:
    """Test the Sensibo coordinator."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][load_int.entry_id]
    assert coordinator.data.parsed["ABC999111"].state == "heat"


async def test_coordinator_errors(hass: HomeAssistant, load_int: ConfigEntry) -> None:
    """Test the Sensibo coordinator errors."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][load_int.entry_id]
    coordinator.data.parsed["ABC999111"].state = "heat"

    assert coordinator.last_update_success is True

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        side_effect=AuthenticationError,
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()  # pylint: disable=protected-access

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        side_effect=SensiboError,
    ):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()  # pylint: disable=protected-access

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=SensiboData(raw={}, parsed={}),
    ):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()  # pylint: disable=protected-access

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=SensiboData(raw={}, parsed={}),
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    assert coordinator.data.parsed["ABC999111"].state == "heat"
    assert coordinator.data.parsed["AAZZAAZZ"].state == "off"
    assert coordinator.last_update_success is False
