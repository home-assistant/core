"""Test the Mitsubishi WF-RAC setup, unload and migrations."""

from unittest.mock import AsyncMock

from pywfrac import WfRacConnectionError

from homeassistant.components.mitsubishi_wf_rac.const import (
    CONF_AIRCO_ID,
    CONF_OPERATOR_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import AIRCO_ID, ENTRY_DATA, ENTRY_OPTIONS, HOST, PORT

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A reachable airco loads, and unloading releases the coordinator."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Retry rather than load half an entry.

    An airco that does not answer at startup gets Home Assistant's automatic
    retry instead of a "loaded" entry with no working entities.
    """
    mock_repository.get_aircon_stats.side_effect = WfRacConnectionError("no route")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_registry_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The airco registers with its MAC, and without a model name.

    ModelNr is a capability grouping rather than a type name, so it goes into
    model_id; "model" staying empty is the point of the assertion.
    """
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, AIRCO_ID), init_integration.entry_id
    )

    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "00:11:22:33:44:aa")}
    assert device.model is None
    assert device.model_id == "1"
    assert device.sw_version == "WF-RAC-HTTPS, mcu: 200, wireless: 025"


async def test_remove_entry_releases_the_account_slot(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The module keeps a small table of controllers; removal frees ours."""
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    mock_repository.del_account_info.assert_awaited_with(AIRCO_ID)


async def test_migration_from_version_1(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """A v1 entry moves its host into options and gains retry tolerance.

    Entries this old exist in the wild through the custom-component release of
    this integration, which shares this domain.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={
            CONF_NAME: "Living room",
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: ENTRY_DATA[CONF_DEVICE_ID],
            CONF_OPERATOR_ID: ENTRY_DATA[CONF_OPERATOR_ID],
            CONF_AIRCO_ID: AIRCO_ID,
        },
        unique_id=AIRCO_ID,
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 5
    assert entry.state is ConfigEntryState.LOADED
    assert entry.options[CONF_HOST] == HOST
    assert CONF_HOST not in entry.data
    # v1 entries ran with no tolerance at all; the module reassociates hourly.
    assert entry.options["availability_retry_limit"] == 3


async def test_migration_lifts_a_retry_limit_below_the_floor(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """A stored limit under the minimum is raised rather than refused."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data=ENTRY_DATA,
        options={**ENTRY_OPTIONS, "availability_retry_limit": 1},
        unique_id=AIRCO_ID,
        version=4,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 5
    assert entry.options["availability_retry_limit"] == 3
