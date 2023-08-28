"""Tests for the Cert Expiry sensors."""
from datetime import timedelta
import socket
import ssl
from unittest.mock import patch

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util.dt import utcnow

from .const import HOST, PORT
from .helpers import future_timestamp, static_datetime

from tests.common import MockConfigEntry, async_fire_time_changed


@patch("homeassistant.util.dt.utcnow", return_value=static_datetime())
async def test_async_setup_entry(mock_now, hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    timestamp = future_timestamp(100)

    with patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")


async def test_async_setup_entry_bad_cert(hass: HomeAssistant) -> None:
    """Test async_setup_entry with a bad/expired cert."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
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

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") == "some error"
    assert not state.attributes.get("is_valid")


async def test_update_sensor(hass: HomeAssistant) -> None:
    """Test async_update for sensor."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    starting_time = static_datetime()
    timestamp = future_timestamp(100)

    with patch("homeassistant.util.dt.utcnow", return_value=starting_time), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=24)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")


async def test_update_sensor_network_errors(hass: HomeAssistant) -> None:
    """Test async_update for sensor."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    starting_time = static_datetime()
    timestamp = future_timestamp(100)

    with patch("homeassistant.util.dt.utcnow", return_value=starting_time), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=24)

    with patch("homeassistant.util.dt.utcnow", return_value=next_update), patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.gaierror,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    next_update = starting_time + timedelta(hours=48)

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == STATE_UNAVAILABLE

    with patch("homeassistant.util.dt.utcnow", return_value=next_update), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=48))
        await hass.async_block_till_done()

        state = hass.states.get("sensor.example_com_cert_expiry")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == timestamp.isoformat()
        assert state.attributes.get("error") == "None"
        assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=72)

    with patch("homeassistant.util.dt.utcnow", return_value=next_update), patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ssl.SSLError("something bad"),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=72))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("error") == "something bad"
    assert not state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=96)

    with patch("homeassistant.util.dt.utcnow", return_value=next_update), patch(
        "homeassistant.components.cert_expiry.helper.get_cert", side_effect=Exception()
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=96))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == STATE_UNAVAILABLE
