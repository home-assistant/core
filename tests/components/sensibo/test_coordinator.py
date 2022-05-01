"""The test for the sensibo coordinator."""
from __future__ import annotations

from unittest.mock import patch

from pysensibo.exceptions import AuthenticationError, SensiboError
from pysensibo.model import SensiboData
import pytest

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.components.sensibo.coordinator import SensiboDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import init_integration
from .response import DATA_FROM_API


async def test_coordinator(hass: HomeAssistant) -> None:
    """Test the Sensibo coordinator."""
    entry = await init_integration(hass, entry_id="hallcd")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.data.parsed["ABC999111"].state == "heat"


async def test_coordinator_errors(hass: HomeAssistant) -> None:
    """Test the Sensibo coordinator errors."""
    entry = await init_integration(hass, entry_id="hallcd2")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data.parsed["ABC999111"].state = "heat"

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
