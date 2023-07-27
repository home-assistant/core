"""Test Ping component setup process."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from icmplib import SocketPermissionError
import pytest

from homeassistant import config as hass_config, setup
from homeassistant.components.ping.const import DOMAIN
from homeassistant.const import SERVICE_RELOAD, STATE_HOME, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, get_fixture_path


async def test_setup_config(
    hass: HomeAssistant, load_yaml_integration: None, mock_ping: None
) -> None:
    """Test setup from yaml."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test_binary_sensor")
    state_tracker = hass.states.get("device_tracker.test_device_tracker")

    assert state_binary_sensor.state == STATE_ON
    assert state_tracker.state == STATE_HOME


async def test_load_integration_no_privilege(
    hass: HomeAssistant, get_config: dict[str, Any], yaml_devices: None
) -> None:
    """Set up the ping integration in Home Assistant unprivileged."""
    with patch(
        "homeassistant.components.ping.icmp_ping", side_effect=SocketPermissionError
    ), patch("homeassistant.components.ping.binary_sensor.async_ping"), patch(
        "homeassistant.components.ping.device_tracker.async_multiping"
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            get_config,
        )
        await hass.async_block_till_done()


async def test_reload_service(
    hass: HomeAssistant,
    load_yaml_integration: None,
    caplog: pytest.LogCaptureFixture,
    mock_ping: None,
) -> None:
    """Test reload serviice."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test_binary_sensor")
    state_tracker = hass.states.get("device_tracker.test_device_tracker")

    assert state_binary_sensor.state == STATE_ON
    assert state_tracker.state == STATE_HOME

    caplog.clear()

    yaml_path = get_fixture_path("configuration.yaml", "ping")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert "Loading config" in caplog.text

    state_binary_sensor = hass.states.get("binary_sensor.test_binary_sensor")
    assert state_binary_sensor.state == STATE_ON

    caplog.clear()

    yaml_path = get_fixture_path("configuration_empty.yaml", "ping")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test_binary_sensor")
    assert not state_binary_sensor

    assert "Loading config" not in caplog.text
