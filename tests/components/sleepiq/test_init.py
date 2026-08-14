"""Tests for the SleepIQ integration."""

from collections.abc import Callable
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock

from asyncsleepiq import (
    SleepIQAPIException,
    SleepIQLoginException,
    SleepIQTimeoutException,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.sleepiq.const import DOMAIN, IS_IN_BED, SLEEP_NUMBER
from homeassistant.components.sleepiq.coordinator import (
    LONGER_UPDATE_INTERVAL,
    SLEEP_DATA_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_USERNAME, PRESSURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import (
    BED_ID,
    SLEEPER_L_ID,
    SLEEPER_L_NAME,
    SLEEPER_L_NAME_LOWER,
    SLEEPIQ_CONFIG,
    setup_platform,
)

from tests.common import (
    MockConfigEntry,
    RegistryEntryWithDefaults,
    async_fire_time_changed,
    mock_registry,
)

ENTITY_IS_IN_BED = f"sensor.sleepnumber_{BED_ID}_{SLEEPER_L_NAME_LOWER}_{IS_IN_BED}"
ENTITY_PRESSURE = f"sensor.sleepnumber_{BED_ID}_{SLEEPER_L_NAME_LOWER}_{PRESSURE}"
ENTITY_SLEEP_NUMBER = (
    f"sensor.sleepnumber_{BED_ID}_{SLEEPER_L_NAME_LOWER}_{SLEEP_NUMBER}"
)


async def test_unload_entry(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test unloading the SleepIQ entry."""
    entry = await setup_platform(hass, "sensor")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_entry_setup_login_error(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client is unable to login."""
    mock_asyncsleepiq.login.side_effect = SleepIQLoginException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_entry_setup_timeout_error(
    hass: HomeAssistant, mock_asyncsleepiq
) -> None:
    """Test when sleepiq client timeout."""
    mock_asyncsleepiq.login.side_effect = SleepIQTimeoutException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_update_interval(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test update interval."""
    await setup_platform(hass, "sensor")
    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 1

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 2


async def test_api_error(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client is unable to login."""
    mock_asyncsleepiq.init_beds.side_effect = SleepIQAPIException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_api_timeout(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client timeout."""
    mock_asyncsleepiq.init_beds.side_effect = SleepIQTimeoutException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


@pytest.mark.parametrize(
    ("get_fetch_mock", "platform", "interval"),
    [
        pytest.param(
            lambda client, bed: client.fetch_bed_statuses,
            "sensor",
            UPDATE_INTERVAL,
            id="bed_status",
        ),
        pytest.param(
            lambda client, bed: bed.fetch_pause_mode,
            "switch",
            LONGER_UPDATE_INTERVAL,
            id="pause_mode",
        ),
        pytest.param(
            lambda client, bed: bed.sleepers[0].fetch_sleep_data,
            "sensor",
            SLEEP_DATA_UPDATE_INTERVAL,
            id="sleep_data",
        ),
    ],
)
async def test_update_auth_error_starts_reauth_flow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
    mock_bed: MagicMock,
    get_fetch_mock: Callable[[MagicMock, MagicMock], MagicMock],
    platform: str,
    interval: timedelta,
) -> None:
    """Test an authentication failure during an update starts the reauth flow."""
    entry = await setup_platform(hass, platform)

    get_fetch_mock(mock_asyncsleepiq, mock_bed).side_effect = SleepIQAPIException(
        HTTPStatus.UNAUTHORIZED, "unauthorized"
    )
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_update_api_error_does_not_start_reauth_flow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test a non-authentication API error during an update does not start reauth."""
    await setup_platform(hass, "sensor")

    mock_asyncsleepiq.fetch_bed_statuses.side_effect = SleepIQAPIException(
        HTTPStatus.INTERNAL_SERVER_ERROR, "server error"
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 2
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_unique_id_migration(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test migration of sensor unique IDs."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=SLEEPIQ_CONFIG,
        unique_id=SLEEPIQ_CONFIG[CONF_USERNAME].lower(),
    )

    mock_entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            ENTITY_IS_IN_BED: RegistryEntryWithDefaults(
                entity_id=ENTITY_IS_IN_BED,
                unique_id=f"{BED_ID}_{SLEEPER_L_NAME}_{IS_IN_BED}",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_PRESSURE: RegistryEntryWithDefaults(
                entity_id=ENTITY_PRESSURE,
                unique_id=f"{BED_ID}_{SLEEPER_L_NAME}_{PRESSURE}",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_SLEEP_NUMBER: RegistryEntryWithDefaults(
                entity_id=ENTITY_SLEEP_NUMBER,
                unique_id=f"{BED_ID}_{SLEEPER_L_NAME}_{SLEEP_NUMBER}",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)  # pylint: disable=home-assistant-tests-registry-fixtures

    sensor_is_in_bed = ent_reg.async_get(ENTITY_IS_IN_BED)
    assert sensor_is_in_bed.unique_id == f"{SLEEPER_L_ID}_{IS_IN_BED}"

    sensor_pressure = ent_reg.async_get(ENTITY_PRESSURE)
    assert sensor_pressure.unique_id == f"{SLEEPER_L_ID}_{PRESSURE}"

    sensor_sleep_number = ent_reg.async_get(ENTITY_SLEEP_NUMBER)
    assert sensor_sleep_number.unique_id == f"{SLEEPER_L_ID}_{SLEEP_NUMBER}"
