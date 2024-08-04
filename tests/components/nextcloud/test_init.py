"""Tests for the Nextcloud init."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nextcloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .const import MOCKED_ENTRY_ID, NC_DATA, VALID_CONFIG

from tests.common import mock_registry


async def test_async_setup_entry(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test a successful setup entry."""
    entry = await init_integration(hass, VALID_CONFIG, NC_DATA)

    assert entry.state == ConfigEntryState.LOADED

    states = hass.states.async_all()
    assert len(states) == 44

    e_reg = er.async_get(hass)

    for state in states:
        assert state.state == snapshot(name=f"{state.entity_id}_state")
        assert state.attributes == snapshot(name=f"{state.entity_id}_attributes")
        assert e_reg.async_get(state.entity_id).unique_id == snapshot(
            name=f"{state.entity_id}_unique_id"
        )


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test migration of unique ids to stable ones."""

    entity_id = "sensor.my_nc_url_local_system_version"

    mock_registry(
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
    reg_entry = er.async_get(hass).async_get(entity_id)
    assert reg_entry.unique_id == f"{VALID_CONFIG[CONF_URL]}#nextcloud_system_version"

    await init_integration(hass, VALID_CONFIG, NC_DATA)

    # test migrated unique id
    reg_entry = er.async_get(hass).async_get(entity_id)
    assert reg_entry.unique_id == f"{MOCKED_ENTRY_ID}#system_version"
