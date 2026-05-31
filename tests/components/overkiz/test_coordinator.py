"""Tests for the Overkiz data update coordinator."""

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.exceptions import MaintenanceException, ServiceUnavailableException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MockOverkizClient, SetupOverkizIntegration

from tests.common import MockConfigEntry, async_fire_time_changed

# A stateful setup so the coordinator polls on the regular update interval
# (a fully stateless setup falls back to a 60 minute interval).
STATEFUL_FIXTURE = "setup/cloud_nexity_rail_din_europe.json"


async def _trigger_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> None:
    """Advance time to trigger a single coordinator refresh."""
    freezer.tick(config_entry.runtime_data.coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _has_reauth(hass: HomeAssistant, config_entry: MockConfigEntry) -> bool:
    """Return whether a reauthentication flow is in progress for the entry."""
    return any(config_entry.async_get_active_flows(hass, {"reauth"}))


@pytest.mark.parametrize(
    "exception",
    [
        ServiceUnavailableException("Server is unavailable."),
        MaintenanceException("Server is down for maintenance"),
    ],
    ids=["service_unavailable", "maintenance"],
)
async def test_transient_server_error_is_retried(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Transient server errors fail the update without reauthenticating."""
    config_entry = await setup_overkiz_integration(fixture=STATEFUL_FIXTURE)
    assert config_entry.state is ConfigEntryState.LOADED

    mock_client.fetch_events.side_effect = exception
    await _trigger_refresh(hass, freezer, config_entry)

    # The entry stays loaded (retried) and no reauth flow is started.
    assert config_entry.state is ConfigEntryState.LOADED
    assert not _has_reauth(hass, config_entry)
