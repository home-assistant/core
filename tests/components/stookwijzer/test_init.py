"""Test the Stookwijzer init."""

from unittest.mock import patch

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.components.stookwijzer.sensor import STOOKWIJZER_SENSORS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock, True, True)

    assert entry.runtime_data is not None
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id is not None

    for description in STOOKWIJZER_SENSORS:
        state = hass.states.get(f"{SENSOR_DOMAIN}.{DOMAIN}_{description.key}")
        assert state.state in {"0", "2", "2.0", "code_yellow"}

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_transform_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock, False)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_unload_config_entry_when_device_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading when the website is unavailable."""
    entry = await setup_integration(hass, aioclient_mock, False)

    assert entry.state is ConfigEntryState.SETUP_ERROR

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test successful migration of entry data."""
    entry = await setup_integration(hass, aioclient_mock, 1, True, False)
    assert entry.version == 1

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2


async def test_migrate_entry_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test successful migration of entry data."""
    with patch(
        "stookwijzer.stookwijzerapi.Stookwijzer.async_transform_coordinates",
        return_value=(None, None),
    ):
        entry = await setup_integration(hass, aioclient_mock, 1, False, True)
        assert entry.version == 1
