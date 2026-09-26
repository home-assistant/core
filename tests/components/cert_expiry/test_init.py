"""Tests for Cert Expiry setup."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.components.cert_expiry.errors import ResolveFailed
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component

from .const import HOST, PORT
from .helpers import certificate_expiring, future_timestamp, static_datetime

SENSOR_ENTITY_ID = "sensor.example_com_cert_expiry"


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
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(future_timestamp(1)),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == f"{HOST}:{PORT}"


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures("cert_verified")
async def test_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    assert hass.state is CoreState.running

    mock_config_entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert mock_config_entry is config_entries[0]

    timestamp = future_timestamp(100)
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is None


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures("cert_verified")
async def test_setup_during_boot_waits_for_started(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the first check waits for Home Assistant to start during boot."""
    hass.set_state(CoreState.not_running)
    mock_config_entry.add_to_hass(hass)

    timestamp = future_timestamp(100)
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ) as mock_get_cert:
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        mock_get_cert.assert_not_called()
        assert hass.states.get(SENSOR_ENTITY_ID) is None

        await hass.async_start()
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.state == timestamp.isoformat()


async def test_setup_during_boot_failure_loads_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a failed first check after boot leaves the entry loaded but unavailable."""
    hass.set_state(CoreState.not_running)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=ResolveFailed(HOST, PORT),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_start()
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(SENSOR_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_setup_retries_on_connection_failure(
    hass: HomeAssistant,
) -> None:
    """Test a connection failure during setup schedules a retry instead of loading."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=ResolveFailed("cannot resolve"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get(SENSOR_ENTITY_ID) is None


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures("cert_verified")
async def test_coordinator_refresh_fails_then_recovers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test coordinator recovers after a periodic refresh fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(future_timestamp(100)),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()

    freezer.move_to(static_datetime() + timedelta(hours=13))
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=ResolveFailed("cannot resolve"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    freezer.move_to(static_datetime() + timedelta(hours=26))
    timestamp = future_timestamp(200)
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("is_valid")
    assert state.attributes.get("error") is None
