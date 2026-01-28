"""Test ISS coordinators."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.iss.const import DEFAULT_TLE_SOURCES, DOMAIN, TLE_SOURCES
from homeassistant.components.iss.coordinator.people import IssPeopleCoordinator
from homeassistant.components.iss.coordinator.position import IssPositionCoordinator
from homeassistant.components.iss.coordinator.tle import IssTleCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

# Sample valid TLE data for ISS
SAMPLE_TLE_LINE1 = (
    "1 25544U 98067A   24001.50000000  .00012345  00000-0  12345-3 0  9999"
)
SAMPLE_TLE_LINE2 = (
    "2 25544  51.6400 123.4567 0001234  12.3456 123.4567 15.49123456123456"
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="iss_unique_id",
    )


class TestIssTleCoordinator:
    """Tests for IssTleCoordinator class."""

    async def test_coordinator_fetch_success(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator successfully fetches TLE data."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssTleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # Mock satellitetle.fetch_latest_tles to return valid TLE data
        # The expected format is: {norad_id: (source, (name, line1, line2))}
        mock_tle_data = ("test_source", ("ISS", SAMPLE_TLE_LINE1, SAMPLE_TLE_LINE2))

        with patch(
            "homeassistant.components.iss.coordinator.tle.fetch_latest_tles",
            return_value={25544: mock_tle_data},
        ):
            result = await coordinator._async_update_data()

        assert result["line1"] == SAMPLE_TLE_LINE1
        assert result["line2"] == SAMPLE_TLE_LINE2
        assert "timestamp" in result

    async def test_coordinator_fetch_failure_with_cache(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator falls back to cache when fetch fails."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssTleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # Mock cached data
        cached_data = {
            "line1": SAMPLE_TLE_LINE1,
            "line2": SAMPLE_TLE_LINE2,
            "timestamp": "2024-01-01T00:00:00",
        }

        with (
            patch.object(coordinator._store, "async_load", return_value=cached_data),
            patch(
                "homeassistant.components.iss.coordinator.tle.fetch_latest_tles",
                side_effect=Exception("Fetch failed"),
            ),
        ):
            result = await coordinator._async_update_data()

        # Should return cached data when fetch fails
        assert result == cached_data

    async def test_coordinator_fetch_failure_no_cache(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator raises error when fetch fails and no cache."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssTleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        with (
            patch.object(coordinator._store, "async_load", return_value=None),
            patch(
                "homeassistant.components.iss.coordinator.tle.fetch_latest_tles",
                side_effect=Exception("Fetch failed"),
            ),
            pytest.raises(UpdateFailed, match="No valid TLE data could be fetched"),
        ):
            await coordinator._async_update_data()

    async def test_coordinator_uses_cache_when_valid(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator uses cache when still valid."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssTleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # Mock recent cached data
        cached_data = {
            "line1": SAMPLE_TLE_LINE1,
            "line2": SAMPLE_TLE_LINE2,
            "timestamp": datetime.now().isoformat(),
        }

        with (
            patch.object(coordinator._store, "async_load", return_value=cached_data),
            patch(
                "homeassistant.components.iss.coordinator.tle.fetch_latest_tles"
            ) as mock_fetch,
        ):
            result = await coordinator._async_update_data()

        # Should use cache without calling fetcher
        mock_fetch.assert_not_called()
        assert result == cached_data

    async def test_coordinator_saves_fresh_data(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator saves freshly fetched data."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssTleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # The expected format is: {norad_id: (source, (name, line1, line2))}
        mock_tle_data = ("test_source", ("ISS", SAMPLE_TLE_LINE1, SAMPLE_TLE_LINE2))

        with (
            patch.object(coordinator._store, "async_load", return_value=None),
            patch(
                "homeassistant.components.iss.coordinator.tle.fetch_latest_tles",
                return_value={25544: mock_tle_data},
            ),
            patch.object(coordinator._store, "async_save") as mock_save,
        ):
            await coordinator._async_update_data()

        # Should save the fresh data
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert saved_data["line1"] == SAMPLE_TLE_LINE1
        assert saved_data["line2"] == SAMPLE_TLE_LINE2
        assert "timestamp" in saved_data

    async def test_coordinator_uses_configured_sources(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator uses sources from configuration."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssTleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        with (
            patch.object(coordinator._store, "async_load", return_value=None),
            patch(
                "homeassistant.components.iss.coordinator.tle.fetch_latest_tles",
                side_effect=Exception("Fetch failed"),
            ) as mock_fetch,
            pytest.raises(UpdateFailed),
        ):
            await coordinator._async_update_data()

        # Verify it was called with correct sources and ISS NORAD ID
        expected_sources = [
            (source, TLE_SOURCES[source])
            for source in DEFAULT_TLE_SOURCES
            if source in TLE_SOURCES
        ]
        mock_fetch.assert_called_once_with([25544], expected_sources)


class TestIssPeopleCoordinator:
    """Tests for IssPeopleCoordinator class."""

    async def test_coordinator_fetch_success(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator successfully fetches people data."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssPeopleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # Mock successful pyiss response
        mock_data = {"number": 7, "people": [{"name": "Alice", "craft": "ISS"}]}

        with patch.object(coordinator._iss, "people_in_space", return_value=mock_data):
            result = await coordinator._async_update_data()

        assert result["number"] == 7
        assert len(result["people"]) == 1
        assert result["people"][0]["name"] == "Alice"

    async def test_coordinator_retry_on_timeout(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator retries on timeout."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssPeopleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # First two attempts fail, third succeeds
        mock_data = {"number": 7, "people": []}

        with (
            patch.object(
                coordinator._iss,
                "people_in_space",
                side_effect=[
                    Exception("Network error"),
                    Exception("Network error"),
                    mock_data,
                ],
            ),
            patch("asyncio.sleep") as mock_sleep,
        ):
            result = await coordinator._async_update_data()

        assert result["number"] == 7
        # Should have slept twice (after first two failures)
        assert mock_sleep.call_count == 2
        # Check exponential backoff: 1 second, then 2 seconds
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    async def test_coordinator_retry_on_client_error(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator retries on client error."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssPeopleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # First attempt fails, second succeeds
        mock_data = {"number": 7, "people": []}

        with (
            patch.object(
                coordinator._iss,
                "people_in_space",
                side_effect=[Exception("Connection error"), mock_data],
            ),
            patch("asyncio.sleep") as mock_sleep,
        ):
            result = await coordinator._async_update_data()

        assert result["number"] == 7
        # Should have slept once (after first failure)
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(1)

    async def test_coordinator_retry_on_http_error(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator retries on HTTP error status."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssPeopleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # First attempt fails with HTTP error, second succeeds
        mock_data = {"number": 7, "people": []}

        with (
            patch.object(
                coordinator._iss,
                "people_in_space",
                side_effect=[Exception("Error server n 500"), mock_data],
            ),
            patch("asyncio.sleep") as mock_sleep,
        ):
            result = await coordinator._async_update_data()

        assert result["number"] == 7
        mock_sleep.assert_called_once_with(1)

    async def test_coordinator_retry_on_invalid_data(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator retries on invalid data."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssPeopleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # First attempt returns invalid data, second succeeds
        mock_data_success = {"number": 7, "people": []}

        with (
            patch.object(
                coordinator._iss,
                "people_in_space",
                side_effect=[{"invalid": "data"}, mock_data_success],
            ),
            patch("asyncio.sleep") as mock_sleep,
        ):
            result = await coordinator._async_update_data()

        assert result["number"] == 7
        mock_sleep.assert_called_once_with(1)

    async def test_coordinator_max_retries_exceeded(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test coordinator fails after max retries."""
        mock_config_entry.add_to_hass(hass)

        coordinator = IssPeopleCoordinator(
            hass,
            config_entry=mock_config_entry,
            update_interval=timedelta(hours=24),
        )

        # All attempts fail
        with (
            patch.object(
                coordinator._iss,
                "people_in_space",
                side_effect=Exception("Network error"),
            ),
            patch("asyncio.sleep") as mock_sleep,
            pytest.raises(
                UpdateFailed, match="Error fetching people in space: Network error"
            ),
        ):
            await coordinator._async_update_data()

        # Should have slept twice (after first two failures, not after third)
        assert mock_sleep.call_count == 2
        # Check exponential backoff: 1 second, then 2 seconds
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    async def test_coordinator_exponential_backoff_capped(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test exponential backoff is capped at max value."""
        mock_config_entry.add_to_hass(hass)

        # Temporarily increase MAX_RETRIES to test backoff cap
        with patch("homeassistant.components.iss.coordinator.people.MAX_RETRIES", 5):
            coordinator = IssPeopleCoordinator(
                hass,
                config_entry=mock_config_entry,
                update_interval=timedelta(hours=24),
            )

            # All attempts fail
            with (
                patch.object(
                    coordinator._iss,
                    "people_in_space",
                    side_effect=Exception("Network error"),
                ),
                patch("asyncio.sleep") as mock_sleep,
                pytest.raises(UpdateFailed),
            ):
                await coordinator._async_update_data()

            # Check that backoff is capped at 8 seconds
            # Sleep calls: 1, 2, 4, 8 (attempts 1-4, not after 5th)
            assert mock_sleep.call_count == 4
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert sleep_calls == [1, 2, 4, 8]  # Capped at MAX_BACKOFF (8)


class TestIssPositionCoordinator:
    """Tests for IssPositionCoordinator class."""

    async def test_position_calculation_success(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test successful position calculation."""
        mock_config_entry.add_to_hass(hass)

        # Mock TLE coordinator with valid data
        mock_tle_coordinator = MagicMock()
        mock_tle_coordinator.data = {
            "line1": SAMPLE_TLE_LINE1,
            "line2": SAMPLE_TLE_LINE2,
        }

        coordinator = IssPositionCoordinator(
            hass,
            config_entry=mock_config_entry,
            tle_coordinator=mock_tle_coordinator,
            update_interval=timedelta(seconds=60),
        )

        with patch(
            "homeassistant.components.iss.coordinator.position.load"
        ) as mock_load:
            mock_ts = MagicMock()
            mock_t = MagicMock()
            mock_ts.now.return_value = mock_t
            mock_load.timescale.return_value = mock_ts

            mock_satellite = MagicMock()
            mock_geocentric = MagicMock()
            mock_subpoint = MagicMock()
            mock_subpoint.latitude.degrees = 51.5074
            mock_subpoint.longitude.degrees = -0.1278

            with patch(
                "homeassistant.components.iss.coordinator.position.EarthSatellite",
                return_value=mock_satellite,
            ):
                mock_satellite.at.return_value = mock_geocentric
                with patch(
                    "homeassistant.components.iss.coordinator.position.wgs84"
                ) as mock_wgs84:
                    mock_wgs84.subpoint.return_value = mock_subpoint

                    result = await coordinator._async_update_data()

                    assert result == {
                        "latitude": "51.5074",
                        "longitude": "-0.1278",
                    }

    async def test_position_calculation_no_tle_data(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test position calculation when TLE data is unavailable."""
        mock_config_entry.add_to_hass(hass)

        # Mock TLE coordinator with no data
        mock_tle_coordinator = MagicMock()
        mock_tle_coordinator.data = None

        coordinator = IssPositionCoordinator(
            hass,
            config_entry=mock_config_entry,
            tle_coordinator=mock_tle_coordinator,
            update_interval=timedelta(seconds=60),
        )

        with pytest.raises(UpdateFailed, match="TLE data not available"):
            await coordinator._async_update_data()
