"""Test the Mitsubishi WF-RAC setup, unload and migrations."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pywfrac import WfRacConnectionError, WfRacError

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


@pytest.mark.usefixtures("hass")
async def test_device_registry_entry(
    init_integration: MockConfigEntry, device_registry: dr.DeviceRegistry
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


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param({}, id="no firmware sections at all"),
        pytest.param({"mcu": "200", "wireless": None}, id="sections of another shape"),
        pytest.param(
            {
                "firmType": None,
                "mcu": {"firmVer": None},
                "wireless": {"firmVer": ""},
            },
            id="sections that carry no revision",
        ),
    ],
)
async def test_a_firmware_version_it_cannot_read_does_not_cost_the_poll(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_config_entry: MockConfigEntry,
    aircon_stat: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    answer: dict[str, Any],
) -> None:
    """These three strings only decorate the device registry.

    Firmware revisions differ in which of the sections they send, and one of
    them shaped differently than expected must not take down a poll that read
    the state block.
    """
    mock_repository.get_aircon_stats.return_value = {
        "airconStat": aircon_stat["airconStat"],
        **answer,
    }

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, AIRCO_ID), mock_config_entry.entry_id
    )

    assert device is not None
    assert device.sw_version == "unknown, mcu: unknown, wireless: unknown"


async def test_remove_entry_releases_the_account_slot(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The module keeps a small table of controllers; removal frees ours."""
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    mock_repository.del_account_info.assert_awaited_with(AIRCO_ID)


@pytest.mark.usefixtures("mock_repository")
async def test_migration_from_version_1(hass: HomeAssistant) -> None:
    """A v1 entry gains retry tolerance and keeps its host where setup reads it.

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

    assert entry.version == 7
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_HOST] == HOST
    assert CONF_HOST not in entry.options
    # v1 entries ran with no tolerance at all; the module reassociates hourly.
    assert entry.options["availability_retry_limit"] == 3


@pytest.mark.usefixtures("mock_repository")
async def test_migration_brings_the_host_back_into_data(hass: HomeAssistant) -> None:
    """An entry that kept its host in options gets it back into data.

    That is where versions 2 to 5 stored it, and where the discovery helper
    refreshing a moved unit never wrote - so the address it merged into data
    was the one setup read, and the edited one in options was not.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={k: v for k, v in ENTRY_DATA.items() if k != CONF_HOST},
        options={**ENTRY_OPTIONS, CONF_HOST: HOST},
        unique_id=AIRCO_ID,
        version=5,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 7
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_HOST] == HOST
    assert CONF_HOST not in entry.options


@pytest.mark.usefixtures("mock_repository")
async def test_migration_lifts_a_retry_limit_below_the_floor(
    hass: HomeAssistant,
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

    assert entry.version == 7
    assert entry.options["availability_retry_limit"] == 3


@pytest.mark.usefixtures("mock_repository")
async def test_migration_lifts_a_retry_limit_the_old_toggle_left_behind(
    hass: HomeAssistant,
) -> None:
    """A v3 entry that ran with no tolerance at all gets some.

    The v1 -> v2 step set the availability check to False while the flag was
    dead code, so these entries went unavailable on the first missed poll -
    which the module's hourly reassociation produces on its own.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data=ENTRY_DATA,
        options={"availability_retry_limit": 1, "availability_retry": 1},
        unique_id=AIRCO_ID,
        version=3,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 7
    assert entry.options["availability_retry_limit"] == 3
    # The key nothing ever read is gone with the step that wrote it.
    assert "availability_retry" not in entry.options


async def test_a_failed_platform_unload_keeps_the_coordinator(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Entities that stayed loaded must keep the coordinator that feeds them.

    Shutting it down anyway would leave a loaded entry that never updates
    again.
    """
    device = init_integration.runtime_data.device

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(init_integration.entry_id)
        await hass.async_block_till_done()

    assert "Failed to unload entry" in caplog.text
    assert device.last_update_success


@pytest.mark.parametrize(
    ("side_effect", "answer"),
    [
        pytest.param(WfRacError("no answer"), None, id="no answer"),
        pytest.param(None, {"result": 2}, id="refused"),
        pytest.param(None, {"result": 429}, id="rate limited"),
        pytest.param(None, {}, id="answered without a result"),
        pytest.param(None, ["ok"], id="answered with something else entirely"),
    ],
)
async def test_removal_says_so_when_the_slot_is_not_released(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception | None,
    answer: Any,
) -> None:
    """The module keeps a small account table, and it can refuse to free ours.

    Nothing here can fix that - the slot has to be freed from the official
    app - so the removal goes through and says what was left behind. A
    refusal has to read as one: it is the case where that advice is needed,
    and the module says so in the same result code add_account() is read by.
    """
    mock_repository.del_account_info.side_effect = side_effect
    mock_repository.del_account_info.return_value = answer

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    assert "Could not release the controller slot" in caplog.text
    # Kept out of the message on purpose: a log this ends up in is usually
    # attached to an issue report.
    assert ENTRY_DATA[CONF_OPERATOR_ID] not in caplog.text


async def test_removal_says_the_slot_is_free_when_the_module_confirms_it(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The other half: a confirmed release is not something to warn about."""
    mock_repository.del_account_info.return_value = {"result": 0}

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    assert "Released the controller slot" in caplog.text


@pytest.mark.usefixtures("mock_repository")
async def test_migration_gives_a_hand_added_entry_the_identity_discovery_uses(
    hass: HomeAssistant,
) -> None:
    """Entries added by hand never registered one.

    The manual step checked for a duplicate airco itself instead, so zeroconf
    could not recognise the entry: a unit that moved was offered as a new
    discovery and its address was never refreshed. The module announces
    itself as <mac>.local and the airco id is that same MAC.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        unique_id=None,
        version=6,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 7
    assert entry.unique_id == AIRCO_ID
