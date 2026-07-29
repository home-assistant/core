"""Test OpenAQ initialization."""

from unittest.mock import MagicMock, patch

from openaq import NotAuthorizedError, ServerError

from homeassistant.components.openaq.const import CONF_LOCATION_ID, DOMAIN
from homeassistant.components.openaq.coordinator import OpenAQDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import setup_integration
from .conftest import API_KEY, LOCATION_ID, make_latest, make_response

from tests.common import MockConfigEntry


async def test_setup_success(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_openaq_client
    assert len(mock_config_entry.runtime_data.coordinators) == 1


async def test_setup_retry_on_first_refresh_failure(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when first coordinator refresh fails."""
    mock_openaq_client.locations.latest.side_effect = ServerError("API error")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_openaq_client.close.assert_called_once()


async def test_setup_retries_on_first_refresh_auth_failure(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when first coordinator refresh has an auth error."""
    mock_openaq_client.locations.latest.side_effect = NotAuthorizedError(
        "Invalid API key"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_openaq_client.close.assert_called_once()


async def test_setup_retry_on_empty_location_response(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when OpenAQ returns no location."""
    mock_openaq_client.locations.get.return_value = make_response([])

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_openaq_client.close.assert_called_once()


async def test_setup_stops_after_a_failed_location_refresh(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
) -> None:
    """Test setup closes after the failed refresh and skips later locations."""
    refreshed_locations: list[int] = []

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: LOCATION_ID},
                subentry_id="ABCDEF",
                subentry_type="location",
                title="Del Norte",
                unique_id=str(LOCATION_ID),
            ),
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: 9999},
                subentry_id="GHIJKL",
                subentry_type="location",
                title="South Valley",
                unique_id="9999",
            ),
        ],
    )

    async def first_refresh(coordinator: OpenAQDataUpdateCoordinator) -> None:
        """Fail the first configured location refresh."""
        refreshed_locations.append(coordinator.location_id)
        raise ConfigEntryNotReady("API error")

    def close_client() -> None:
        """Assert the failing refresh finished before closing the client."""
        assert refreshed_locations == [LOCATION_ID]

    mock_openaq_client.close.side_effect = close_client

    with patch(
        "homeassistant.components.openaq.OpenAQDataUpdateCoordinator.async_config_entry_first_refresh",
        first_refresh,
    ):
        await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert refreshed_locations == [LOCATION_ID]
    mock_openaq_client.close.assert_called_once()


async def test_coordinators_share_client_lock(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
) -> None:
    """Test coordinators share the lock for the shared client."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: LOCATION_ID},
                subentry_id="ABCDEF",
                subentry_type="location",
                title="Del Norte",
                unique_id=str(LOCATION_ID),
            ),
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: 9999},
                subentry_id="GHIJKL",
                subentry_type="location",
                title="South Valley",
                unique_id="9999",
            ),
        ],
    )
    await setup_integration(hass, config_entry)
    coordinators = list(config_entry.runtime_data.coordinators.values())

    assert coordinators[0]._client_lock is coordinators[1]._client_lock


async def test_setup_fetches_location_data(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator fetches OpenAQ location data."""
    await setup_integration(hass, mock_config_entry)

    mock_openaq_client.locations.get.assert_called_once_with(LOCATION_ID)
    mock_openaq_client.locations.latest.assert_called_once_with(LOCATION_ID)
    mock_openaq_client.locations.sensors.assert_called_once_with(LOCATION_ID)


async def test_refresh_uses_cached_location_metadata(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
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
    mock_openaq_client.locations.latest.assert_called_once_with(LOCATION_ID)


async def test_unload_closes_client(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading OpenAQ closes the client."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_openaq_client.close.assert_called_once()


async def test_update_listener_reloads_entry(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
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
    hass: HomeAssistant, mock_openaq_client: MagicMock
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
