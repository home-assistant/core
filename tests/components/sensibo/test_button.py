"""The test for the sensibo button platform."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pysensibo.model import SensiboData
from pytest import MonkeyPatch, raises

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_button(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: MonkeyPatch,
    get_data: SensiboData,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo button."""

    state_button = hass.states.get("button.hallway_reset_filter")
    state_filter_clean = hass.states.get("binary_sensor.hallway_filter_clean_required")
    state_filter_last_reset = hass.states.get("sensor.hallway_filter_last_reset")

    assert state_button.state is STATE_UNKNOWN
    assert state_filter_clean.state is STATE_ON
    assert state_filter_last_reset.state == "2022-03-12T15:24:26+00:00"

    freezer.move_to(datetime(2022, 6, 19, 20, 0, 0))

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_reset_filter",
        return_value={"status": "success"},
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: state_button.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "filter_clean", False)
    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "filter_last_reset",
        datetime(2022, 6, 19, 20, 0, 0, tzinfo=dt.UTC),
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state_button = hass.states.get("button.hallway_reset_filter")
    state_filter_clean = hass.states.get("binary_sensor.hallway_filter_clean_required")
    state_filter_last_reset = hass.states.get("sensor.hallway_filter_last_reset")
    assert (
        state_button.state == datetime(2022, 6, 19, 20, 0, 0, tzinfo=dt.UTC).isoformat()
    )
    assert state_filter_clean.state is STATE_OFF
    assert state_filter_last_reset.state == "2022-06-19T20:00:00+00:00"


async def test_button_failure(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo button fails."""

    state_button = hass.states.get("button.hallway_reset_filter")

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_reset_filter",
        return_value={"status": "failure"},
    ):
        with raises(HomeAssistantError):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {
                    ATTR_ENTITY_ID: state_button.entity_id,
                },
                blocking=True,
            )
