"""The test for the sensibo coordinator."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.exceptions import AuthenticationError, SensiboError
from pysensibo.model import SensiboData
import pytest

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, get_data: SensiboData
) -> None:
    """Test the Sensibo coordinator with errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="username",
        version=2,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
    ) as mock_data, patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        monkeypatch.setattr(get_data.parsed["ABC999111"], "hvac_mode", "heat")
        monkeypatch.setattr(get_data.parsed["ABC999111"], "device_on", True)
        mock_data.return_value = get_data
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("climate.hallway")
        assert state.state == "heat"
        mock_data.reset_mock()

        mock_data.side_effect = SensiboError("info")
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("climate.hallway")
        assert state.state == STATE_UNAVAILABLE
        mock_data.reset_mock()

        mock_data.return_value = SensiboData(raw={}, parsed={})
        mock_data.side_effect = None
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("climate.hallway")
        assert state.state == STATE_UNAVAILABLE
        mock_data.reset_mock()

        monkeypatch.setattr(get_data.parsed["ABC999111"], "hvac_mode", "heat")
        monkeypatch.setattr(get_data.parsed["ABC999111"], "device_on", True)

        mock_data.return_value = get_data
        mock_data.side_effect = None
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("climate.hallway")
        assert state.state == "heat"
        mock_data.reset_mock()

        mock_data.side_effect = AuthenticationError("info")
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=7))
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("climate.hallway")
        assert state.state == STATE_UNAVAILABLE
