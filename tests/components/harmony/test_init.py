"""Test init of Logitch Harmony Hub integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from aioharmony.exceptions import TimeOut
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    RegistryEntryWithDefaults,
    mock_registry,
)

from homeassistant.components.harmony import async_setup_entry
from homeassistant.components.harmony.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.setup import async_setup_component

from .conftest import FakeHarmonyClient
from .const import (
    ENTITY_NILE_TV,
    ENTITY_PLAY_MUSIC,
    ENTITY_SELECT,
    ENTITY_WATCH_TV,
    HUB_NAME,
    NILE_TV_ACTIVITY_ID,
    PLAY_MUSIC_ACTIVITY_ID,
    WATCH_TV_ACTIVITY_ID,
)


async def test_unique_id_migration(
    mock_hc, hass: HomeAssistant, mock_write_config
) -> None:
    """Test migration of switch unique ids to stable ones."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    mock_registry(
        hass,
        {
            # old format
            ENTITY_WATCH_TV: RegistryEntryWithDefaults(
                entity_id=ENTITY_WATCH_TV,
                unique_id="123443-Watch TV",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # old format, activity name with -
            ENTITY_NILE_TV: RegistryEntryWithDefaults(
                entity_id=ENTITY_NILE_TV,
                unique_id="123443-Nile-TV",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # new format
            ENTITY_PLAY_MUSIC: RegistryEntryWithDefaults(
                entity_id=ENTITY_PLAY_MUSIC,
                unique_id=f"activity_{PLAY_MUSIC_ACTIVITY_ID}",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # old entity which no longer has a matching activity on the hub. skipped.
            "switch.some_other_activity": RegistryEntryWithDefaults(
                entity_id="switch.some_other_activity",
                unique_id="123443-Some Other Activity",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # select entity
            ENTITY_SELECT: RegistryEntryWithDefaults(
                entity_id=ENTITY_SELECT,
                unique_id=f"{HUB_NAME}_activities",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)  # pylint: disable=home-assistant-tests-registry-fixtures

    switch_tv = ent_reg.async_get(ENTITY_WATCH_TV)
    assert switch_tv.unique_id == f"activity_{WATCH_TV_ACTIVITY_ID}"

    switch_nile = ent_reg.async_get(ENTITY_NILE_TV)
    assert switch_nile.unique_id == f"activity_{NILE_TV_ACTIVITY_ID}"

    switch_music = ent_reg.async_get(ENTITY_PLAY_MUSIC)
    assert switch_music.unique_id == f"activity_{PLAY_MUSIC_ACTIVITY_ID}"

    select_activities = ent_reg.async_get(ENTITY_SELECT)
    assert select_activities.unique_id == f"{HUB_NAME}_activities"


@pytest.mark.usefixtures("mock_hc")
async def test_connect_timeout_retries_setup(
    hass: HomeAssistant,
    harmony_client: FakeHarmonyClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a hub that times out on connect closes the client and retries setup."""
    harmony_client.connect = AsyncMock(side_effect=TimeOut)
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    harmony_client.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_hc", "mock_write_config")
async def test_reconfigure_loaded_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring a loaded entry reloads it once with the new host."""
    mock_config_entry.add_to_hass(hass)
    harmonyapi = MagicMock(connect=AsyncMock(return_value=True), close=AsyncMock())
    harmonyapi.hub_id = 123
    with (
        patch(
            "homeassistant.components.harmony.async_setup_entry",
            wraps=async_setup_entry,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.harmony.util.HarmonyAPI",
            return_value=harmonyapi,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.1"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.address == "192.0.2.1"
    # Initial setup plus a single reload by the update listener
    assert mock_setup_entry.await_count == 2


@pytest.mark.usefixtures("mock_hc", "mock_write_config")
async def test_ssdp_host_change_reloads_loaded_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovering a loaded hub on a new host reloads it once."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.harmony.async_setup_entry",
            wraps=async_setup_entry,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.harmony.config_flow.HubConnector.get_remote_id",
            return_value=123,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_SSDP},
            data=SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                ssdp_location="http://192.0.2.1:8088/description",
                upnp={"friendlyName": HUB_NAME},
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.address == "192.0.2.1"
    assert mock_setup_entry.await_count == 2
