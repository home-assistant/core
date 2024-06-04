"""Test setting up and unloading PrusaLink."""

from datetime import timedelta
from unittest.mock import patch

from pyprusalink.types import InvalidAuth, PrusaLinkError
import pytest

from homeassistant.components.prusalink import DOMAIN
from homeassistant.components.prusalink.config_flow import ConfigFlow
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("mock_api")


async def test_unloading(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test unloading prusalink."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert hass.states.async_entity_ids_count() > 0

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    for state in hass.states.async_all():
        assert state.state == "unavailable"


@pytest.mark.parametrize("exception", [InvalidAuth, PrusaLinkError])
async def test_failed_update(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, exception
) -> None:
    """Test failed update marks prusalink unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    with (
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_version",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_status",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_legacy_printer",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_job",
            side_effect=exception,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30), fire_all=True)
        await hass.async_block_till_done()

    for state in hass.states.async_all():
        assert state.state == "unavailable"


async def test_migration_from_1_1_to_1_2(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test migrating from version 1 to 2."""
    data = {
        CONF_HOST: "http://prusaxl.local",
        CONF_API_KEY: "api-key",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)

    # Ensure that we have username, password after migration
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        **data,
        CONF_USERNAME: "maker",
        CONF_PASSWORD: "api-key",
    }
    # Make sure that we don't have any issues
    assert len(issue_registry.issues) == 0


async def test_migration_from_1_1_to_1_2_outdated_firmware(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test migrating from version 1.1 to 1.2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://prusaxl.local",
            CONF_API_KEY: "api-key",
        },
        version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "pyprusalink.PrusaLink.get_info",
        side_effect=InvalidAuth,  # Simulate firmware update required
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.minor_version == 1
    assert (DOMAIN, "firmware_5_1_required") in issue_registry.issues

    # Reloading the integration with a working API (e.g. User updated firmware)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Integration should be running now, the issue should be gone
    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert (DOMAIN, "firmware_5_1_required") not in issue_registry.issues


async def test_migration_fails_on_future_version(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test migrating fails on a version higher than the current one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        version=ConfigFlow.VERSION + 1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
