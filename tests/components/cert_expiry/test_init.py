"""Tests for Cert Expiry setup."""
from datetime import timedelta

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import HOST, PORT
from .helpers import future_timestamp, static_datetime

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_with_config(hass):
    """Test setup component with config."""
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


async def test_update_unique_id(hass):
    """Test updating a config entry without a unique_id."""
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

    assert entry.state == ENTRY_STATE_LOADED
    assert entry.unique_id == f"{HOST}:{PORT}"


@patch("homeassistant.util.dt.utcnow", return_value=static_datetime())
async def test_unload_config_entry(mock_now, hass):
    """Test unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    with patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=future_timestamp(100),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_LOADED
    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state.state == "100"
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state == ENTRY_STATE_NOT_LOADED
    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is None
