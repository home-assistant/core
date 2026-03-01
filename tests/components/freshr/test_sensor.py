"""Test the Fresh-r sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from pyfreshr.exceptions import LoginError, ScrapeError
from pyfreshr.models import DeviceReadings, DeviceSummary
import pytest

from homeassistant.components.freshr.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import DEVICE_ID

from tests.common import MockConfigEntry


def _make_client(current: DeviceReadings) -> MagicMock:
    """Build a minimal FreshrClient mock returning a single device."""
    client = MagicMock()
    client.logged_in = False
    client.login = AsyncMock()
    client.fetch_devices = AsyncMock(return_value=[DeviceSummary(id=DEVICE_ID)])
    client.fetch_device_current = AsyncMock(return_value=current)
    return client


@pytest.mark.usefixtures("init_integration")
async def test_sensor_entities_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that all sensor entities are created for each device."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 6
    unique_ids = {e.unique_id for e in entries}
    assert unique_ids == {
        f"{DEVICE_ID}_t1",
        f"{DEVICE_ID}_t2",
        f"{DEVICE_ID}_co2",
        f"{DEVICE_ID}_hum",
        f"{DEVICE_ID}_flow",
        f"{DEVICE_ID}_dp",
    }


@pytest.mark.usefixtures("init_integration")
async def test_sensor_states(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor states match the coordinator data."""

    def get_state(key: str) -> str | None:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{DEVICE_ID}_{key}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state.state

    assert get_state("t1") == "21.5"
    assert get_state("t2") == "5.3"
    assert get_state("co2") == "850"
    assert get_state("hum") == "45"
    assert get_state("flow") == "0.12"
    assert get_state("dp") == "10.2"


async def test_sensor_none_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors return unknown when coordinator data is None."""
    with patch(
        "homeassistant.components.freshr.coordinator.FreshrClient",
        return_value=_make_client(
            DeviceReadings(t1=None, t2=None, co2=None, hum=None, flow=None, dp=None)
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    for key in ("t1", "t2", "co2", "hum", "dp"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{DEVICE_ID}_{key}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "unknown"


async def test_sensor_invalid_numeric_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors return unknown when numeric conversion fails."""
    with patch(
        "homeassistant.components.freshr.coordinator.FreshrClient",
        return_value=_make_client(
            DeviceReadings(
                t1="not-a-number",
                t2="not-a-number",
                co2="not-a-number",
                hum="not-a-number",
                flow=0.05,
                dp="not-a-number",
            )
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    for key in ("t1", "t2", "co2", "hum", "dp"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{DEVICE_ID}_{key}"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == "unknown"

    flow_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{DEVICE_ID}_flow")
    assert flow_id is not None
    assert hass.states.get(flow_id).state == "0.05"


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> None:
    """Test that a LoginError during setup raises ConfigEntryAuthFailed."""
    mock_freshr_client.login = AsyncMock(side_effect=LoginError("bad credentials"))
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_scrape_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> None:
    """Test that a ScrapeError during setup triggers a retry."""
    mock_freshr_client.fetch_devices = AsyncMock(side_effect=ScrapeError("parse error"))
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> None:
    """Test that a ClientError during setup triggers a retry."""
    mock_freshr_client.fetch_devices = AsyncMock(
        side_effect=ClientError("network error")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> None:
    """Test that an empty device list triggers a retry."""
    mock_freshr_client.fetch_devices = AsyncMock(return_value=[])
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_sensor_device_disappears(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors return unknown when a device is no longer in coordinator data."""
    coordinator = mock_config_entry.runtime_data
    coordinator.data = {}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{DEVICE_ID}_t1")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
