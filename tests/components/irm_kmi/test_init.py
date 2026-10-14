"""Tests for the IRM KMI integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from irm_kmi_api import IrmKmiApiError
import pytest

from homeassistant.components.irm_kmi.const import CONF_LANGUAGE_OVERRIDE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import WEATHER_ENTITY_ID

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the IRM KMI configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("hass_language", "options", "expected_manufacturer"),
    [
        pytest.param(
            "nl",
            {},
            "Koninklijk Meteorologisch Instituut van België",
            id="home_assistant_language",
        ),
        pytest.param(
            "nl",
            {CONF_LANGUAGE_OVERRIDE: "fr"},
            "Institut Royal Météorologique de Belgique",
            id="language_override",
        ),
        pytest.param(
            "es",
            {},
            "Royal Meteorological Institute of Belgium",
            id="unsupported_language_falls_back_to_english",
        ),
    ],
)
@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_device_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_language: str,
    options: dict[str, str],
    expected_manufacturer: str,
) -> None:
    """Test the device entry."""
    hass.config.language = hass_language
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert device_entry.manufacturer == expected_manufacturer


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the IRM KMI configuration entry not ready."""
    mock_irm_kmi_api.refresh_forecasts_coord.side_effect = IrmKmiApiError

    await setup_integration(hass, mock_config_entry)

    assert mock_irm_kmi_api.refresh_forecasts_coord.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    # The first refresh has no last success time to compare the grace period to
    assert "Unexpected error fetching" not in caplog.text


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_entity_unavailable_after_grace_period(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_forecasts_coord: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the last known data is only served for the grace period."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(WEATHER_ENTITY_ID).state != STATE_UNAVAILABLE

    mock_get_forecasts_coord.side_effect = IrmKmiApiError

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY_ID).state != STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=7))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY_ID).state != STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=7))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_get_forecasts_coord.side_effect = None

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY_ID).state != STATE_UNAVAILABLE


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_grace_period_starts_at_the_last_usable_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the grace period runs from the last refresh that produced data."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(WEATHER_ENTITY_ID).state != STATE_UNAVAILABLE

    mock_irm_kmi_api.get_daily_forecast.side_effect = TypeError

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_irm_kmi_api.refresh_forecasts_coord.side_effect = IrmKmiApiError

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY_ID).state == STATE_UNAVAILABLE
