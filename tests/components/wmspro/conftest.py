"""Common fixtures for the wmspro tests."""

from collections.abc import AsyncGenerator, Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest
from wmspro.action import Action, ActionList

from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import remove_config_entry

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> AsyncGenerator[MockConfigEntry]:
    """Return a dummy config entry."""
    mock_config_entry = MockConfigEntry(
        title="WebControl",
        domain=DOMAIN,
        data={CONF_HOST: "webcontrol"},
    )
    yield mock_config_entry

    # cleanup after test if not already done by test itself
    if hass.config_entries.async_get_entry(mock_config_entry.entry_id):
        await remove_config_entry(hass, mock_config_entry)


@pytest.fixture
async def mock_setup_entry() -> AsyncGenerator[AsyncMock]:
    """Override async_setup_entry."""

    hass: HomeAssistant | None = None
    config_entry: MockConfigEntry | None = None

    def fake_setup_entry(local_hass, local_entry):
        nonlocal hass, config_entry
        hass = local_hass
        config_entry = local_entry
        return True

    with patch(
        "homeassistant.components.wmspro.async_setup_entry",
        wraps=fake_setup_entry,
    ) as mock_setup_entry:
        yield mock_setup_entry

    # cleanup after test if not already done by test itself
    if (
        hass
        and config_entry
        and hass.config_entries.async_get_entry(config_entry.entry_id)
    ):
        await remove_config_entry(hass, config_entry)


@pytest.fixture
def mock_hub_ping() -> Generator[AsyncMock]:
    """Override WebControlPro.ping."""
    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ) as mock_hub_ping:
        yield mock_hub_ping


@pytest.fixture
def mock_hub_refresh() -> Generator[AsyncMock]:
    """Override WebControlPro.refresh."""
    with patch(
        "wmspro.webcontrol.WebControlPro.refresh",
        return_value=True,
    ) as mock_hub_refresh:
        yield mock_hub_refresh


@pytest.fixture
async def mock_hub_configuration(
    request: pytest.FixtureRequest, hass: HomeAssistant
) -> AsyncGenerator[AsyncMock]:
    """Override WebControlPro._getConfiguration with a param fixture file."""
    hub_config = await async_load_json_object_fixture(hass, request.param, DOMAIN)
    with patch(
        "wmspro.webcontrol.WebControlPro._getConfiguration",
        return_value=hub_config,
    ) as mock_hub_configuration:
        mock_hub_configuration.configure_mock(**hub_config)
        yield mock_hub_configuration


@pytest.fixture
async def mock_hub_status(
    request: pytest.FixtureRequest, hass: HomeAssistant
) -> AsyncGenerator[AsyncMock]:
    """Override WebControlPro._getStatus with a param fixture file."""
    hub_status = await async_load_json_object_fixture(hass, request.param, DOMAIN)
    with patch(
        "wmspro.webcontrol.WebControlPro._getStatus",
        return_value=hub_status,
    ) as mock_hub_status:
        mock_hub_status.configure_mock(**hub_status)
        yield mock_hub_status


@pytest.fixture
def mock_dest_refresh() -> Generator[AsyncMock]:
    """Override Destination.refresh."""
    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ) as mock_dest_refresh:
        yield mock_dest_refresh


@pytest.fixture
def mock_action_call() -> Generator[Callable]:
    """Override Action.__call__."""

    async def fake_call(self, **kwargs):
        self._update_params(kwargs)

    with patch.object(
        Action,
        "__call__",
        side_effect=fake_call,
        autospec=True,
    ) as mock_action_call:
        yield mock_action_call


@pytest.fixture
def mock_action_list_call() -> Generator[Callable]:
    """Override ActionList.__call__."""

    async def fake_list_call(self, **kwargs):
        # fake action list call via individual action calls
        for args in self:
            dest = self._control.dests[args["destinationId"]]
            await dest.actions[args["actionId"]](**args["parameters"])

    with patch.object(
        ActionList,
        "__call__",
        side_effect=fake_list_call,
        autospec=True,
    ) as mock_action_list_call:
        yield mock_action_list_call


@pytest.fixture
def mock_scene_call() -> Generator[AsyncMock]:
    """Override Scene.__call__."""
    with patch(
        "wmspro.scene.Scene.__call__",
    ) as mock_scene_call:
        yield mock_scene_call
