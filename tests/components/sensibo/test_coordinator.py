"""The test for the sensibo coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysensibo.exceptions import AuthenticationError, SensiboError
from pysensibo.model import SensiboData

from homeassistant.components.climate import HVACMode
from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator(
    hass: HomeAssistant,
    mock_client: MagicMock,
    get_data: tuple[SensiboData, dict[str, Any], dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo coordinator with errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="firstnamelastname",
        version=2,
    )

    config_entry.add_to_hass(hass)

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].hvac_mode = "heat"
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].device_on = True

    mock_data = mock_client.async_get_devices_data
    mock_data.return_value = get_data[0]
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_data.assert_called_once()
    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT
    mock_data.reset_mock()

    mock_data.side_effect = SensiboError("info")
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_data.assert_called_once()
    state = hass.states.get("climate.hallway")
    assert state.state == STATE_UNAVAILABLE
    mock_data.reset_mock()

    mock_data.return_value = SensiboData(raw={}, parsed={})
    mock_data.side_effect = None
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_data.assert_called_once()
    state = hass.states.get("climate.hallway")
    assert state.state == STATE_UNAVAILABLE
    mock_data.reset_mock()

    mock_data.return_value = get_data[0]
    mock_data.side_effect = None
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_data.assert_called_once()
    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT
    mock_data.reset_mock()

    mock_data.side_effect = AuthenticationError("info")
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_data.assert_called_once()
    state = hass.states.get("climate.hallway")
    assert state.state == STATE_UNAVAILABLE
