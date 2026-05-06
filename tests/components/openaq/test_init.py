"""Test OpenAQ initialization."""

import asyncio
from unittest.mock import AsyncMock, patch

from openaq import ServerError

from homeassistant.components.openaq.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import (
    API_KEY,
    LOCATION_ID,
    make_latest,
    make_location,
    make_response,
    make_sensor,
)

from tests.common import MockConfigEntry


async def test_setup_success(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_openaq_client
    assert len(mock_config_entry.runtime_data.coordinators) == 1


async def test_setup_retry_on_first_refresh_failure(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when first coordinator refresh fails."""
    mock_openaq_client.locations.latest.side_effect = ServerError("API error")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_openaq_client.close.assert_awaited_once()


async def test_setup_retry_on_empty_location_response(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when OpenAQ returns no location."""
    mock_openaq_client.locations.get.return_value = make_response([])

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_openaq_client.close.assert_awaited_once()


async def test_setup_fetches_location_data_concurrently(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator fetches independent OpenAQ location data concurrently."""
    started: set[str] = set()
    location_started = asyncio.Event()
    latest_started = asyncio.Event()
    sensors_started = asyncio.Event()
    release = asyncio.Event()

    async def wait_for_release(
        name: str, started_event: asyncio.Event, response: object
    ) -> object:
        """Return a response after all location data requests have started."""
        started.add(name)
        started_event.set()
        await release
        return response

    async def get_location(_location_id: int) -> object:
        """Return the location response."""
        return await wait_for_release(
            "location", location_started, make_response([make_location()])
        )

    async def get_latest(_location_id: int) -> object:
        """Return the latest measurements response."""
        return await wait_for_release(
            "latest", latest_started, make_response([make_latest(1, 8.5)])
        )

    async def get_sensors(_location_id: int) -> object:
        """Return the sensors response."""
        return await wait_for_release(
            "sensors", sensors_started, make_response([make_sensor(1, "pm25")])
        )

    mock_openaq_client.locations.get.side_effect = get_location
    mock_openaq_client.locations.latest.side_effect = get_latest
    mock_openaq_client.locations.sensors.side_effect = get_sensors

    setup_task = asyncio.create_task(setup_integration(hass, mock_config_entry))
    await asyncio.wait_for(
        asyncio.gather(
            location_started.wait(),
            latest_started.wait(),
            sensors_started.wait(),
        ),
        timeout=1,
    )
    assert started == {"location", "latest", "sensors"}
    release.set()

    await asyncio.wait_for(setup_task, timeout=1)


async def test_refresh_uses_cached_location_metadata(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refresh polls latest measurements without refetching metadata."""
    await setup_integration(hass, mock_config_entry)
    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    mock_openaq_client.locations.get.reset_mock()
    mock_openaq_client.locations.latest.reset_mock()
    mock_openaq_client.locations.sensors.reset_mock()
    mock_openaq_client.locations.latest.return_value = make_response(
        [make_latest(2, 21.2)]
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    mock_openaq_client.locations.get.assert_not_called()
    mock_openaq_client.locations.sensors.assert_not_called()
    mock_openaq_client.locations.latest.assert_awaited_once_with(LOCATION_ID)


async def test_unload_closes_client(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading OpenAQ closes the client."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_openaq_client.close.assert_awaited_once()


async def test_update_listener_reloads_entry(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry updates reload the entry."""
    await setup_integration(hass, mock_config_entry)

    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        hass.config_entries.async_update_entry(
            mock_config_entry,
            data={CONF_API_KEY: "new-api-key"},
        )
        await hass.async_block_till_done()

    mock_reload.assert_awaited_once_with(mock_config_entry.entry_id)


async def test_setup_without_locations(
    hass: HomeAssistant, mock_openaq_client: AsyncMock
) -> None:
    """Test setup before any location subentries are configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
    )

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.coordinators == {}
