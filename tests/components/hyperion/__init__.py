"""Tests for the Hyperion component."""
from __future__ import annotations

from types import TracebackType
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from hyperion import const

from homeassistant.components.hyperion.const import CONF_PRIORITY, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

TEST_HOST = "test"
TEST_PORT = const.DEFAULT_PORT_JSON + 1
TEST_PORT_UI = const.DEFAULT_PORT_UI + 1
TEST_INSTANCE = 1
TEST_ID = "default"
TEST_SYSINFO_ID = "f9aab089-f85a-55cf-b7c1-222a72faebe9"
TEST_SYSINFO_VERSION = "2.0.0-alpha.8"
TEST_PRIORITY = 180
TEST_ENTITY_ID_1 = "light.test_instance_1"
TEST_ENTITY_ID_2 = "light.test_instance_2"
TEST_ENTITY_ID_3 = "light.test_instance_3"
TEST_PRIORITY_LIGHT_ENTITY_ID_1 = "light.test_instance_1_priority"
TEST_TITLE = f"{TEST_HOST}:{TEST_PORT}"

TEST_TOKEN = "sekr1t"
TEST_CONFIG_ENTRY_ID = "74565ad414754616000674c87bdc876c"
TEST_CONFIG_ENTRY_OPTIONS: dict[str, Any] = {CONF_PRIORITY: TEST_PRIORITY}

TEST_INSTANCE_1: dict[str, Any] = {
    "friendly_name": "Test instance 1",
    "instance": 1,
    "running": True,
}
TEST_INSTANCE_2: dict[str, Any] = {
    "friendly_name": "Test instance 2",
    "instance": 2,
    "running": True,
}
TEST_INSTANCE_3: dict[str, Any] = {
    "friendly_name": "Test instance 3",
    "instance": 3,
    "running": True,
}

TEST_AUTH_REQUIRED_RESP: dict[str, Any] = {
    "command": "authorize-tokenRequired",
    "info": {
        "required": True,
    },
    "success": True,
    "tan": 1,
}

TEST_AUTH_NOT_REQUIRED_RESP = {
    **TEST_AUTH_REQUIRED_RESP,
    "info": {"required": False},
}


class AsyncContextManagerMock(Mock):
    """An async context manager mock for Hyperion."""

    async def __aenter__(self) -> AsyncContextManagerMock | None:
        """Enter context manager and connect the client."""
        result = await self.async_client_connect()
        return self if result else None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Leave context manager and disconnect the client."""
        await self.async_client_disconnect()


def create_mock_client() -> Mock:
    """Create a mock Hyperion client."""
    mock_client = AsyncContextManagerMock()
    # pylint: disable=attribute-defined-outside-init
    mock_client.async_client_connect = AsyncMock(return_value=True)
    mock_client.async_client_disconnect = AsyncMock(return_value=True)
    mock_client.async_is_auth_required = AsyncMock(
        return_value=TEST_AUTH_NOT_REQUIRED_RESP
    )
    mock_client.async_login = AsyncMock(
        return_value={"command": "authorize-login", "success": True, "tan": 0}
    )

    mock_client.async_sysinfo_id = AsyncMock(return_value=TEST_SYSINFO_ID)
    mock_client.async_sysinfo_version = AsyncMock(return_value=TEST_SYSINFO_VERSION)
    mock_client.async_client_switch_instance = AsyncMock(return_value=True)
    mock_client.async_client_login = AsyncMock(return_value=True)
    mock_client.async_get_serverinfo = AsyncMock(
        return_value={
            "command": "serverinfo",
            "success": True,
            "tan": 0,
            "info": {"fake": "data"},
        }
    )

    mock_client.priorities = []
    mock_client.adjustment = None
    mock_client.effects = None
    mock_client.instances = [
        {"friendly_name": "Test instance 1", "instance": 0, "running": True}
    ]

    return mock_client


def add_test_config_entry(
    hass: HomeAssistantType,
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> ConfigEntry:
    """Add a test config entry."""
    config_entry: MockConfigEntry = MockConfigEntry(  # type: ignore[no-untyped-call]
        entry_id=TEST_CONFIG_ENTRY_ID,
        domain=DOMAIN,
        data=data
        or {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
        },
        title=f"Hyperion {TEST_SYSINFO_ID}",
        unique_id=TEST_SYSINFO_ID,
        options=options or TEST_CONFIG_ENTRY_OPTIONS,
    )
    config_entry.add_to_hass(hass)  # type: ignore[no-untyped-call]
    return config_entry


async def setup_test_config_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry | None = None,
    hyperion_client: Mock | None = None,
    options: dict[str, Any] | None = None,
) -> ConfigEntry:
    """Add a test Hyperion entity to hass."""
    config_entry = config_entry or add_test_config_entry(hass, options=options)

    hyperion_client = hyperion_client or create_mock_client()
    # pylint: disable=attribute-defined-outside-init
    hyperion_client.instances = [TEST_INSTANCE_1]

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=hyperion_client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry


def call_registered_callback(
    client: AsyncMock, key: str, *args: Any, **kwargs: Any
) -> None:
    """Call Hyperion entity callbacks that were registered with the client."""
    for call in client.add_callbacks.call_args_list:
        if key in call[0][0]:
            call[0][0][key](*args, **kwargs)
