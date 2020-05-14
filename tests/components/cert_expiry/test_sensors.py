"""Tests for the Cert Expiry sensors."""
from datetime import timedelta
import socket
import ssl

from asynctest import patch

from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
import homeassistant.util.dt as dt_util

from .const import HOST, PORT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_setup_entry(hass):
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain="cert_expiry",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.sensor.get_cert_time_to_expiry",
        return_value=100,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")


async def test_async_setup_entry_bad_cert(hass):
    """Test async_setup_entry with a bad/expired cert."""
    entry = MockConfigEntry(
        domain="cert_expiry",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ssl.SSLError("some error"),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "0"
    assert state.attributes.get("error") == "some error"
    assert not state.attributes.get("is_valid")


async def test_async_setup_entry_host_unavailable(hass):
    """Test async_setup_entry when host is unavailable."""
    entry = MockConfigEntry(
        domain="cert_expiry",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.gaierror,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is None

    next_update = dt_util.utcnow() + timedelta(seconds=45)
    async_fire_time_changed(hass, next_update)
    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.gaierror,
    ):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is None


async def test_update_sensor(hass):
    """Test async_update for sensor."""
    entry = MockConfigEntry(
        domain="cert_expiry",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.sensor.get_cert_time_to_expiry",
        return_value=100,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")

    next_update = dt_util.utcnow() + timedelta(hours=12)
    async_fire_time_changed(hass, next_update)

    with patch(
        "homeassistant.components.cert_expiry.sensor.get_cert_time_to_expiry",
        return_value=99,
    ):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "99"
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")


async def test_update_sensor_network_errors(hass):
    """Test async_update for sensor."""
    entry = MockConfigEntry(
        domain="cert_expiry",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.sensor.get_cert_time_to_expiry",
        return_value=100,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")

    next_update = dt_util.utcnow() + timedelta(hours=12)
    async_fire_time_changed(hass, next_update)

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.gaierror,
    ):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state.state == STATE_UNAVAILABLE

    next_update = dt_util.utcnow() + timedelta(hours=12)
    async_fire_time_changed(hass, next_update)

    with patch(
        "homeassistant.components.cert_expiry.sensor.get_cert_time_to_expiry",
        return_value=99,
    ):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "99"
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")

    next_update = dt_util.utcnow() + timedelta(hours=12)
    async_fire_time_changed(hass, next_update)

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ssl.SSLError("something bad"),
    ):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "0"
    assert state.attributes.get("error") == "something bad"
    assert not state.attributes.get("is_valid")

    next_update = dt_util.utcnow() + timedelta(hours=12)
    async_fire_time_changed(hass, next_update)

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert", side_effect=Exception()
    ):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state.state == STATE_UNAVAILABLE
