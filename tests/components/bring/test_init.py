"""Unit tests for the bring integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from bring_api import (
    BringAuthException,
    BringListResponse,
    BringParseException,
    BringRequestException,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.bring import async_setup_entry
from homeassistant.components.bring.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .conftest import UUID

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


async def setup_integration(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Mock setup of the bring integration."""
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_bring_client")
async def test_load_unload(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    await setup_integration(hass, bring_config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert bring_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(bring_config_entry.entry_id)
    assert bring_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (BringRequestException, ConfigEntryState.SETUP_RETRY),
        (BringAuthException, ConfigEntryState.SETUP_ERROR),
        (BringParseException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_init_failure(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    status: ConfigEntryState,
    exception: Exception,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test an initialization error on integration load."""
    mock_bring_client.login.side_effect = exception
    await setup_integration(hass, bring_config_entry)
    assert bring_config_entry.state == status


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (BringRequestException, ConfigEntryNotReady),
        (BringAuthException, ConfigEntryAuthFailed),
        (BringParseException, ConfigEntryNotReady),
    ],
)
async def test_init_exceptions(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    exception: Exception,
    expected: Exception,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test an initialization error on integration load."""
    bring_config_entry.add_to_hass(hass)
    mock_bring_client.login.side_effect = exception

    with pytest.raises(expected):
        await async_setup_entry(hass, bring_config_entry)


@pytest.mark.parametrize("exception", [BringRequestException, BringParseException])
@pytest.mark.parametrize(
    "bring_method",
    [
        "load_lists",
        "get_list",
        "get_all_user_settings",
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    exception: Exception,
    bring_method: str,
) -> None:
    """Test config entry not ready."""
    getattr(mock_bring_client, bring_method).side_effect = exception
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("exception", [BringRequestException, BringParseException])
async def test_config_entry_not_ready_udpdate_failed(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test config entry not ready from update failed in _async_update_data."""
    mock_bring_client.load_lists.side_effect = [
        mock_bring_client.load_lists.return_value,
        exception,
    ]
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (BringAuthException, ConfigEntryState.SETUP_ERROR),
        (BringRequestException, ConfigEntryState.SETUP_RETRY),
        (BringParseException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_config_entry_not_ready_auth_error(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    exception: Exception | None,
    state: ConfigEntryState,
) -> None:
    """Test config entry not ready from authentication error."""

    mock_bring_client.load_lists.side_effect = [
        mock_bring_client.load_lists.return_value,
        exception,
    ]

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is state


@pytest.mark.usefixtures("mock_bring_client")
async def test_coordinator_skips_deactivated(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_bring_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the coordinator skips fetching lists for deactivated lists."""
    await setup_integration(hass, bring_config_entry)

    assert bring_config_entry.state is ConfigEntryState.LOADED

    assert mock_bring_client.get_list.await_count == 2

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{UUID}_b4776778-7f6c-496e-951b-92a35d3db0dd")}
    )
    device_registry.async_update_device(device.id, disabled_by=ConfigEntryDisabler.USER)

    mock_bring_client.get_list.reset_mock()

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_bring_client.get_list.await_count == 1


async def test_purge_devices(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing device entry of deleted list."""
    list_uuid = "b4776778-7f6c-496e-951b-92a35d3db0dd"
    await setup_integration(hass, bring_config_entry)

    assert bring_config_entry.state is ConfigEntryState.LOADED

    assert device_registry.async_get_device(
        {(DOMAIN, f"{bring_config_entry.unique_id}_{list_uuid}")}
    )

    mock_bring_client.load_lists.return_value = BringListResponse.from_json(
        load_fixture("lists2.json", DOMAIN)
    )

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device(
            {(DOMAIN, f"{bring_config_entry.unique_id}_{list_uuid}")}
        )
        is None
    )


async def test_create_devices(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test create device entry for new lists."""
    list_uuid = "b4776778-7f6c-496e-951b-92a35d3db0dd"
    mock_bring_client.load_lists.return_value = BringListResponse.from_json(
        load_fixture("lists2.json", DOMAIN)
    )
    await setup_integration(hass, bring_config_entry)

    assert bring_config_entry.state is ConfigEntryState.LOADED

    assert (
        device_registry.async_get_device(
            {(DOMAIN, f"{bring_config_entry.unique_id}_{list_uuid}")}
        )
        is None
    )

    mock_bring_client.load_lists.return_value = BringListResponse.from_json(
        load_fixture("lists.json", DOMAIN)
    )
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get_device(
        {(DOMAIN, f"{bring_config_entry.unique_id}_{list_uuid}")}
    )
