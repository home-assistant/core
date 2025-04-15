"""MadVR conftest for shared testing setup."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.madvr.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import MOCK_CONFIG, MOCK_MAC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.madvr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_madvr_client() -> Generator[AsyncMock]:
    """Mock a MadVR client."""
    with (
        patch(
            "homeassistant.components.madvr.config_flow.Madvr", autospec=True
        ) as mock_client,
        patch("homeassistant.components.madvr.Madvr", new=mock_client),
    ):
        client = mock_client.return_value
        client.host = MOCK_CONFIG[CONF_HOST]
        client.port = MOCK_CONFIG[CONF_PORT]
        client.mac_address = MOCK_MAC
        client.connected.return_value = True
        client.is_device_connectable.return_value = True
        client.loop = AsyncMock()
        client.tasks = AsyncMock()
        client.set_update_callback = MagicMock()

        # mock the property to be off on startup (which it is)
        is_on_mock = PropertyMock(return_value=True)
        type(client).is_on = is_on_mock

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=MOCK_MAC,
        title=DEFAULT_NAME,
        entry_id="3bd2acb0e4f0476d40865546d0d91132",
    )


def get_update_callback(mock_client: MagicMock):
    """Retrieve the update callback function from the mocked client.

    This function extracts the callback that was passed to set_update_callback
    on the mocked MadVR client. This callback is typically the handle_push_data
    method of the MadVRCoordinator.

    Args:
        mock_client (MagicMock): The mocked MadVR client.

    Returns:
        function: The update callback function.

    """
    # Get all the calls made to set_update_callback
    calls = mock_client.set_update_callback.call_args_list

    if not calls:
        raise ValueError("set_update_callback was not called on the mock client")

    # Get the first (and usually only) call
    first_call = calls[0]

    # Get the first argument of this call, which should be the callback function
    return first_call.args[0]
