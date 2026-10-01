"""Test the Daikin Onecta coordinator."""
from datetime import datetime
from datetime import time
from datetime import timedelta
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from daikin_onecta import OnectaRateLimitError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from tests.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import OnectaDataUpdateCoordinator
from homeassistant.components.daikin_onecta.coordinator import OnectaRuntimeData


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="daikin_onecta", unique_id="12345")
    entry.runtime_data = OnectaRuntimeData(daikin_api=MagicMock(), devices={})
    entry.runtime_data.coordinator = MagicMock()
    return entry


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_config_entry):
    """Return a coordinator with test options."""
    config_entry = mock_config_entry
    config_entry.add_to_hass(hass)
    options = {
        "low_scan_interval": 30,  # minutes
        "high_scan_interval": 10,  # minutes
        "high_scan_start": "07:00:00",
        "low_scan_start": "22:00:00",
    }
    hass.config_entries.async_update_entry(config_entry, options=options)
    return OnectaDataUpdateCoordinator(hass, config_entry)


class TestOnectaDataUpdateCoordinator:
    """Test OnectaDataUpdateCoordinator class."""

    def test_in_between_normal_range(self, coordinator):
        """Time within a simple range not crossing midnight."""
        start = time(8, 0, 0)
        end = time(10, 0, 0)
        assert not coordinator.in_between(time(7, 0, 0), start, end)
        assert coordinator.in_between(time(8, 0, 0), start, end)
        assert coordinator.in_between(time(9, 0, 0), start, end)
        assert not coordinator.in_between(time(10, 0, 0), start, end)
        assert not coordinator.in_between(time(11, 0, 0), start, end)

    def test_in_between_overnight_range(self, coordinator):
        """Time within a range that crosses midnight."""
        start = time(22, 0, 0)
        end = time(7, 0, 0)
        assert coordinator.in_between(time(6, 0, 0), start, end)
        assert not coordinator.in_between(time(7, 0, 0), start, end)
        assert not coordinator.in_between(time(12, 0, 0), start, end)
        assert coordinator.in_between(time(22, 0, 0), start, end)
        assert coordinator.in_between(time(23, 0, 0), start, end)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_high_scan_interval(self, mock_now, coordinator, hass: HomeAssistant):
        """High scan interval should apply during high-frequency window."""
        mock_now.return_value = datetime(2023, 1, 1, 10, 0, 0)

        expected = timedelta(minutes=10)
        result = coordinator.determine_update_interval(hass)
        assert result == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_low_scan_interval(self, mock_now, coordinator, hass: HomeAssistant):
        """Low scan interval should apply outside transition windows."""
        mock_now.return_value = datetime(2023, 1, 1, 23, 0, 0)

        with patch.object(coordinator, "in_between", side_effect=[False, False]):
            expected = timedelta(minutes=30)
            result = coordinator.determine_update_interval(hass)
            assert result == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    @patch("homeassistant.components.daikin_onecta.coordinator.random")
    def test_transition_period_randomization(self, mock_random, mock_now, coordinator, hass: HomeAssistant):
        """During transition, interval is randomized between floor and low interval."""
        mock_now.return_value = datetime(2023, 1, 1, 22, 5, 0)
        mock_random.randint.return_value = 120  # 2 minutes

        with patch.object(coordinator, "in_between", side_effect=[False, True]):
            expected = timedelta(seconds=120)
            result = coordinator.determine_update_interval(hass)
            assert result == expected
            mock_random.randint.assert_called_once_with(60, 1800)

    async def test_rate_limit_uses_update_failed_retry_after(self, coordinator, mock_config_entry):
        """A Daikin rate limit should use the coordinator retry-after mechanism."""
        daikin_api = mock_config_entry.runtime_data.daikin_api
        daikin_api._last_patch_call = None
        daikin_api.get_cloud_device_details = AsyncMock(side_effect=OnectaRateLimitError(3060))

        # Simulate daily rate limit reached
        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data()

        assert exc_info.value.retry_after == 3060
        assert coordinator.update_interval == timedelta(minutes=10)

    def test_update_settings(self, coordinator, mock_config_entry, hass: HomeAssistant):
        """Apply changed polling options to the coordinator."""
        options = {
            "low_scan_interval": 45,
            "high_scan_interval": 15,
            "high_scan_start": "07:00:00",
            "low_scan_start": "22:00:00",
        }
        updated_entry = MockConfigEntry(domain=DOMAIN, title="daikin_onecta", unique_id="12345", options=options)

        with patch.object(coordinator, "determine_update_interval", return_value=timedelta(minutes=45)) as determine:
            coordinator.update_settings(updated_entry)

        assert coordinator.options == options
        assert coordinator.update_interval == timedelta(minutes=45)
        determine.assert_called_once_with(hass)
