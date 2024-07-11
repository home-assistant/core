"""The test for the sensibo update platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.model import SensiboData
import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_update(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo update."""

    state1 = hass.states.get("update.hallway_firmware")
    state2 = hass.states.get("update.kitchen_firmware")
    assert state1.state == STATE_ON
    assert state1.attributes["installed_version"] == "SKY30046"
    assert state1.attributes["latest_version"] == "SKY30048"
    assert state1.attributes["title"] == "skyv2"
    assert state2.state == STATE_OFF

    monkeypatch.setattr(get_data.parsed["ABC999111"], "fw_ver", "SKY30048")

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("update.hallway_firmware")
    assert state1.state == STATE_OFF
