"""Tests for setting up the Meraki integration."""

import asyncio
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from meraki.aio import AsyncDashboardAPI
from meraki.aio.api.networks import AsyncNetworks
from meraki.aio.api.organizations import AsyncOrganizations
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_array_fixture

from homeassistant.components.meraki.const import DOMAIN
from homeassistant.components.meraki.coordinator import MAX_PARALLEL_REQUESTS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import api_error, setup_integration


async def test_load_unload(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client is closed when the entry is unloaded."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_meraki_client.__aexit__.assert_awaited_once()


async def test_client_closed_on_stop(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client is closed when Home Assistant stops."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_meraki_client.__aexit__.assert_awaited_once()


@pytest.mark.parametrize(
    ("status", "state"),
    [
        pytest.param(401, ConfigEntryState.SETUP_ERROR, id="invalid_auth"),
        pytest.param(503, ConfigEntryState.SETUP_RETRY, id="cannot_connect"),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    status: int,
    state: ConfigEntryState,
) -> None:
    """Test API errors during setup."""
    mock_meraki_client.organizations.getOrganizationNetworks.side_effect = api_error(
        status
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_setup_timeout(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the update takes too long."""

    async def _never_returns(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        await asyncio.Event().wait()
        return []

    mock_meraki_client.networks.getNetworkClients.side_effect = _never_returns
    with patch("homeassistant.components.meraki.coordinator.UPDATE_TIMEOUT", 0):
        await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_all_requests_finish_before_failing(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client is only closed once every network's request finished."""
    networks = await async_load_json_array_fixture(hass, "networks.json", DOMAIN)
    networks[1]["productTypes"] = ["wireless"]
    mock_meraki_client.organizations.getOrganizationNetworks.return_value = networks
    first_failing = asyncio.Event()
    running: set[str] = set()

    async def _get_clients(network_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        if network_id == networks[0]["id"]:
            first_failing.set()
            raise api_error(503)
        running.add(network_id)
        await first_failing.wait()
        # Slower than the error takes to reach config entry setup.
        for _ in range(100):
            await asyncio.sleep(0)
        running.discard(network_id)
        return []

    mock_meraki_client.networks.getNetworkClients.side_effect = _get_clients
    running_when_closed: list[set[str]] = []
    mock_meraki_client.__aexit__.side_effect = lambda *args: running_when_closed.append(
        set(running)
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert running_when_closed == [set()]


async def test_parallel_requests_limited(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test only a few requests to the organization run at the same time."""
    network = (await async_load_json_array_fixture(hass, "networks.json", DOMAIN))[0]
    mock_meraki_client.organizations.getOrganizationNetworks.return_value = [
        {**network, "id": f"N_{index}"} for index in range(10)
    ]
    running = 0
    most_running = 0

    async def _get_clients(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        nonlocal running, most_running
        running += 1
        most_running = max(most_running, running)
        await asyncio.sleep(0)
        running -= 1
        return []

    mock_meraki_client.networks.getNetworkClients.side_effect = _get_clients
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_meraki_client.networks.getNetworkClients.await_count == 10
    assert most_running == MAX_PARALLEL_REQUESTS


async def test_real_client_writes_no_files(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the library client writes no files, prints nothing and logs via HA."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    networks = await async_load_json_array_fixture(hass, "networks.json", DOMAIN)
    clients = await async_load_json_array_fixture(hass, "clients.json", DOMAIN)

    with (
        patch.object(
            AsyncOrganizations,
            "getOrganizationNetworks",
            new_callable=AsyncMock,
            return_value=networks,
        ),
        patch.object(
            AsyncNetworks,
            "getNetworkClients",
            new_callable=AsyncMock,
            return_value=clients,
        ),
    ):
        await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    client = mock_config_entry.runtime_data.client
    assert isinstance(client, AsyncDashboardAPI)
    assert client._session._smart_flow is None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert client._session._client.is_closed

    assert list(tmp_path.iterdir()) == []
    assert not any(Path(hass.config.config_dir).glob("meraki_api_*.log"))
    assert capsys.readouterr().out == ""
    assert logging.getLogger("meraki.aio").handlers == []
