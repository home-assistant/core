"""Tests for the Cert Expiry sensors."""

from datetime import timedelta
import socket
import ssl
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util.dt import utcnow

from .const import HOST, PORT
from .helpers import future_timestamp, static_datetime

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time(static_datetime())
async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    timestamp = future_timestamp(100)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
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
        "homeassistant.components.cert_expiry.helper.async_get_cert",
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

    with (
        freeze_time(starting_time),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=24)
    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
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

    with (
        freeze_time(starting_time),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=24)

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=socket.gaierror,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    next_update = starting_time + timedelta(hours=48)

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == STATE_UNAVAILABLE

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=48))
        await hass.async_block_till_done()

        state = hass.states.get("sensor.example_com_cert_expiry")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == timestamp.isoformat()
        assert state.attributes.get("error") is None
        assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=72)

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=ssl.SSLError("something bad"),
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=72))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("error") == "something bad"
    assert not state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=96)

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=Exception(),
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=96))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == STATE_UNAVAILABLE


async def test_error_attribute_is_none_when_cert_valid(hass: HomeAssistant) -> None:
    """Test that the error attribute is None (not the string 'None') for a valid cert.

    Regression test: previously str(None) produced the misleading string "None"
    even when no error had occurred.
    """
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    starting_time = static_datetime()
    timestamp = future_timestamp(100)

    # Start with a valid cert — error should be None, not "None"
    with (
        freeze_time(starting_time),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid") is True

    # Simulate a cert error on next poll
    next_update = starting_time + timedelta(hours=12)
    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=ssl.SSLError("certificate has expired"),
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=12))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.attributes.get("error") == "certificate has expired"
    assert state.attributes.get("is_valid") is False

    # Cert becomes valid again — error must return to None, not "None"
    next_update = starting_time + timedelta(hours=24)
    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid") is True


async def test_async_setup_entry_empty_cert(hass: HomeAssistant) -> None:
    """Test setup when peer certificate is empty (e.g. verify_mode=CERT_NONE)."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        return_value={},
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") is not None
    assert not state.attributes.get("is_valid")


async def test_non_default_port(hass: HomeAssistant) -> None:
    """Test sensor naming and unique_id when a non-default port is used."""
    assert hass.state is CoreState.running

    non_default_port = 8443
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: non_default_port},
        unique_id=f"{HOST}:{non_default_port}",
    )

    timestamp = future_timestamp(100)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_8443_cert_expiry")
    assert state is not None
    assert state.state == timestamp.isoformat()
    assert entry.unique_id == f"{HOST}:{non_default_port}"
