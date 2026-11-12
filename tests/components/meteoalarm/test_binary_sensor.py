"""Tests for the MeteoAlarm binary sensor platform."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.meteoalarm.binary_sensor import (
    CONF_PROVINCE,
    SCAN_INTERVAL,
)
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_LANGUAGE,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ALERT

ENTITY_ID = "binary_sensor.test_alert"

CONFIG = {
    BINARY_SENSOR_DOMAIN: {
        CONF_PLATFORM: "meteoalarm",
        CONF_COUNTRY: "NL",
        CONF_PROVINCE: "Test province",
        CONF_LANGUAGE: "en-GB",
        CONF_NAME: "Test alert",
    }
}

pytestmark = pytest.mark.freeze_time("2026-01-01T12:00:00+00:00")


async def test_active_alert(
    hass: HomeAssistant, mock_meteoalert: MagicMock, snapshot: SnapshotAssertion
) -> None:
    """Test the sensor is on and exposes the alert while it has not expired."""
    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    mock_meteoalert.assert_called_once_with("NL", "Test province", "en-GB")
    assert hass.states.get(ENTITY_ID) == snapshot


@pytest.mark.parametrize(
    "alert",
    [
        pytest.param({}, id="no_alert"),
        pytest.param(
            ALERT | {"expires": "2026-01-01T11:59:59+00:00"}, id="expired_alert"
        ),
        pytest.param(ALERT | {"expires": "not a date"}, id="invalid_expires"),
    ],
)
async def test_no_active_alert(
    hass: HomeAssistant,
    mock_meteoalert: MagicMock,
    snapshot: SnapshotAssertion,
    alert: dict[str, Any],
) -> None:
    """Test the sensor is off, without alert attributes, if no alert is valid."""
    mock_meteoalert.return_value.get_alert.return_value = alert

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) == snapshot


async def test_alert_without_expires(
    hass: HomeAssistant, mock_meteoalert: MagicMock
) -> None:
    """Test an alert without an expiration time is active."""
    alert = dict(ALERT)
    del alert["expires"]
    mock_meteoalert.return_value.get_alert.return_value = alert

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["event"] == ALERT["event"]
    assert "expires" not in state.attributes


async def test_defaults(hass: HomeAssistant, mock_meteoalert: MagicMock) -> None:
    """Test the default name and language."""
    config = {
        BINARY_SENSOR_DOMAIN: {
            CONF_PLATFORM: "meteoalarm",
            CONF_COUNTRY: "NL",
            CONF_PROVINCE: "Test province",
        }
    }

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    mock_meteoalert.assert_called_once_with("NL", "Test province", "en")
    assert hass.states.get("binary_sensor.meteoalarm") is not None


async def test_unknown_country_or_province(
    hass: HomeAssistant,
    mock_meteoalert: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test no sensor is created if the library rejects the configuration."""
    mock_meteoalert.side_effect = KeyError

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    assert "Wrong country digits or province name" in caplog.text
    assert hass.states.get(ENTITY_ID) is None


async def test_alert_expires(
    hass: HomeAssistant, mock_meteoalert: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the sensor turns off once the alert in the feed has expired."""
    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # The feed keeps returning the same alert after it has expired at 18:00.
    freezer.move_to("2026-01-01T18:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert "event" not in state.attributes


async def test_alert_withdrawn(
    hass: HomeAssistant, mock_meteoalert: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the sensor turns off when the alert is no longer in the feed."""
    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, CONFIG)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_meteoalert.return_value.get_alert.return_value = {}
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert "event" not in state.attributes
