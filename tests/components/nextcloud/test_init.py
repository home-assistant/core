"""Tests for the Nextcloud init."""

from unittest.mock import patch

from nextcloudmonitor import (
    NextcloudMonitorAuthorizationError,
    NextcloudMonitorConnectionError,
    NextcloudMonitorError,
    NextcloudMonitorRequestError,
)
import pytest

from homeassistant.components.nextcloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, mock_config_entry
from .const import MOCKED_ENTRY_ID, NC_DATA, VALID_CONFIG

from tests.common import mock_registry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_async_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test a successful setup entry."""
    assert await init_integration(hass, VALID_CONFIG, NC_DATA)


async def test_unique_id_migration(
    hass: HomeAssistant,
) -> None:
    """Test migration of unique ids to stable ones."""

    entity_id = "sensor.my_nc_url_local_system_version"

    entity_registry = mock_registry(
        hass,
        {
            entity_id: er.RegistryEntry(
                entity_id=entity_id,
                unique_id=f"{VALID_CONFIG[CONF_URL]}#nextcloud_system_version",
                platform=DOMAIN,
                config_entry_id=MOCKED_ENTRY_ID,
            ),
        },
    )

    # test old unique id
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry.unique_id == f"{VALID_CONFIG[CONF_URL]}#nextcloud_system_version"

    await init_integration(hass, VALID_CONFIG, NC_DATA)

    # test migrated unique id
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry.unique_id == f"{MOCKED_ENTRY_ID}#system_version"


@pytest.mark.parametrize(
    ("exception", "expcted_entry_state"),
    [
        (NextcloudMonitorAuthorizationError, ConfigEntryState.SETUP_ERROR),
        (NextcloudMonitorConnectionError, ConfigEntryState.SETUP_RETRY),
        (NextcloudMonitorRequestError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    exception: NextcloudMonitorError,
    expcted_entry_state: ConfigEntryState,
) -> None:
    """Test a successful setup entry."""

    entry = mock_config_entry(VALID_CONFIG)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nextcloud.NextcloudMonitor", side_effect=exception
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state == expcted_entry_state
