"""Tests for Cert Expiry setup."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import HOST, PORT
from .helpers import future_timestamp, static_datetime

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_with_config(hass: HomeAssistant) -> None:
    """Test setup component with config."""
    assert hass.state is CoreState.running

    config = {
        SENSOR_DOMAIN: [
            {"platform": DOMAIN, CONF_HOST: HOST, CONF_PORT: PORT},
            {"platform": DOMAIN, CONF_HOST: HOST, CONF_PORT: 888},
        ],
    }
    assert await async_setup_component(hass, SENSOR_DOMAIN, config) is True
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    next_update = dt_util.utcnow() + timedelta(seconds=20)
    async_fire_time_changed(hass, next_update)

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=future_timestamp(1),
    ):
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_update_unique_id(hass: HomeAssistant) -> None:
    """Test updating a config entry without a unique_id."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT})
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]
    assert not entry.unique_id

    with patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=future_timestamp(1),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == f"{HOST}:{PORT}"


@patch("homeassistant.util.dt.utcnow", return_value=static_datetime())
async def test_unload_config_entry(mock_now, hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    timestamp = future_timestamp(100)
    with patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is None


async def test_delay_load_during_startup(hass: HomeAssistant) -> None:
    """Test delayed loading of a config entry during startup."""
    hass.state = CoreState.not_running

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT})
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    assert hass.state is CoreState.not_running
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is None

    timestamp = future_timestamp(100)
    with patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        await hass.async_start()
        await hass.async_block_till_done()

    assert hass.state is CoreState.running

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")
