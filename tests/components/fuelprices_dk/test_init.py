"""Test initialization for Fuelprices.dk."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.fuelprices_dk import (
    _update_listener,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.fuelprices_dk.const import (
    CONF_COMPANY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_STATION

from tests.common import MockConfigEntry


async def test_update_listener_schedules_reload(hass: HomeAssistant) -> None:
    """Test update listener schedules an entry reload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: TEST_API_KEY})
    config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload_mock:
        await _update_listener(hass, config_entry)

    reload_mock.assert_called_once_with(config_entry.entry_id)


async def test_async_setup_entry_creates_coordinator(hass: HomeAssistant) -> None:
    """Test setup creates coordinators from station subentries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id=f"{TEST_COMPANY}_{TEST_STATION['id']}",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                },
            )
        ],
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fuelprices_dk.APIClient") as mock_api_client,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ) as forward_mock,
    ):
        coordinator = mock_api_client.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()

        assert await async_setup_entry(hass, config_entry) is True
        assert len(config_entry.runtime_data) == 1
        coordinator.async_config_entry_first_refresh.assert_awaited_once()
        forward_mock.assert_awaited_once()


async def test_async_setup_entry_skips_non_station_subentries(
    hass: HomeAssistant,
) -> None:
    """Test setup skips unsupported subentry types."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="other",
                title="Other",
                unique_id="other_1",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                },
            )
        ],
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fuelprices_dk.APIClient") as mock_api_client,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ) as forward_mock,
    ):
        assert await async_setup_entry(hass, config_entry) is True
        assert config_entry.runtime_data == {}
        mock_api_client.assert_not_called()
        forward_mock.assert_awaited_once()


async def test_async_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Test setup and unload forward platforms."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id="station_1",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                },
            )
        ],
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fuelprices_dk.APIClient") as mock_api_client,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
    ):
        mock_api_client.return_value.async_config_entry_first_refresh = AsyncMock()
        assert await async_setup_entry(hass, config_entry) is True
        assert len(config_entry.runtime_data) == 1
        assert await async_unload_entry(hass, config_entry) is True
