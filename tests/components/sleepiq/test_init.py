"""Tests for the SleepIQ integration."""

from asyncsleepiq import (
    SleepIQAPIException,
    SleepIQLoginException,
    SleepIQTimeoutException,
)

from homeassistant.components.sleepiq.const import (
    DOMAIN,
    IS_IN_BED,
    PRESSURE,
    SLEEP_NUMBER,
)
from homeassistant.components.sleepiq.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
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

    ent_reg = er.async_get(hass)

    sensor_is_in_bed = ent_reg.async_get(ENTITY_IS_IN_BED)
    assert sensor_is_in_bed.unique_id == f"{SLEEPER_L_ID}_{IS_IN_BED}"

    sensor_pressure = ent_reg.async_get(ENTITY_PRESSURE)
    assert sensor_pressure.unique_id == f"{SLEEPER_L_ID}_{PRESSURE}"

    sensor_sleep_number = ent_reg.async_get(ENTITY_SLEEP_NUMBER)
    assert sensor_sleep_number.unique_id == f"{SLEEPER_L_ID}_{SLEEP_NUMBER}"
