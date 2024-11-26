"""Common fixtures for the wmspro tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a dummy config entry."""
    return MockConfigEntry(
        title="WebControl",
        domain=DOMAIN,
        data={CONF_HOST: "webcontrol"},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.wmspro.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


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
def mock_hub_configuration_test() -> Generator[AsyncMock]:
    """Override WebControlPro.configuration."""
    with patch(
        "wmspro.webcontrol.WebControlPro._getConfiguration",
        return_value=load_json_object_fixture("example_config_test.json", DOMAIN),
    ) as mock_hub_configuration:
        yield mock_hub_configuration


@pytest.fixture
def mock_hub_configuration_prod() -> Generator[AsyncMock]:
    """Override WebControlPro._getConfiguration."""
    with patch(
        "wmspro.webcontrol.WebControlPro._getConfiguration",
        return_value=load_json_object_fixture("example_config_prod.json", DOMAIN),
    ) as mock_hub_configuration:
        yield mock_hub_configuration


@pytest.fixture
def mock_hub_status_prod_awning() -> Generator[AsyncMock]:
    """Override WebControlPro._getStatus."""
    with patch(
        "wmspro.webcontrol.WebControlPro._getStatus",
        return_value=load_json_object_fixture(
            "example_status_prod_awning.json", DOMAIN
        ),
    ) as mock_dest_refresh:
        yield mock_dest_refresh


@pytest.fixture
def mock_hub_status_prod_dimmer() -> Generator[AsyncMock]:
    """Override WebControlPro._getStatus."""
    with patch(
        "wmspro.webcontrol.WebControlPro._getStatus",
        return_value=load_json_object_fixture(
            "example_status_prod_dimmer.json", DOMAIN
        ),
    ) as mock_dest_refresh:
        yield mock_dest_refresh


@pytest.fixture
def mock_dest_refresh() -> Generator[AsyncMock]:
    """Override Destination.refresh."""
    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ) as mock_dest_refresh:
        yield mock_dest_refresh


@pytest.fixture
def mock_action_call() -> Generator[AsyncMock]:
    """Override Action.__call__."""

    async def fake_call(self, **kwargs):
        self._update_params(kwargs)

    with patch(
        "wmspro.action.Action.__call__",
        fake_call,
    ) as mock_action_call:
        yield mock_action_call


@pytest.fixture
def mock_scene_call() -> Generator[AsyncMock]:
    """Override Scene.__call__."""
    with patch(
        "wmspro.scene.Scene.__call__",
    ) as mock_scene_call:
        yield mock_scene_call
