"""Fixtures for the Poolside integration tests."""

from base64 import b64encode
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from aiopoolside import PoolsideControl, PoolsideDevice, PoolsideGroup, PoolsideSite
from aiopoolside.const import ControlType, GroupKind
import pytest

from homeassistant.components.poolside.const import (
    CONF_CLIENT_NAME,
    CONF_CLIENT_PRIVATE_KEY,
    CONF_CONTROLLER_PUBLIC_KEY,
    CONF_CONTROLLER_UUID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.50"
TEST_PORT = 8126
TEST_CLIENT_NAME = "Home Assistant Test"
TEST_CONTROLLER_UUID = "11111111-1111-1111-1111-111111111111"
TEST_CLIENT_PRIVATE_KEY = b64encode(b"\x01" * 32).decode()
TEST_CONTROLLER_PUBLIC_KEY = b64encode(b"\x02" * 32).decode()
TEST_SITE_NAME = "Test Residence"
TEST_SITE_UUID = "site-1"
TEST_SITE = PoolsideSite(uuid=TEST_SITE_UUID, name=TEST_SITE_NAME)

TEST_BODY_OF_WATER_UUID = "body-pool"

DEFAULT_GROUP = PoolsideGroup(
    uuid="group-pool",
    name="Pool",
    kind=GroupKind.BODY_OF_WATER,
    body_of_water_uuid=TEST_BODY_OF_WATER_UUID,
    body_of_water_type="POOL",
)


def make_group(
    uuid: str,
    name: str,
    kind: GroupKind | None = GroupKind.BODY_OF_WATER,
    body_of_water_uuid: str | None = None,
    body_of_water_type: str | None = None,
) -> PoolsideGroup:
    """Build a PoolsideGroup for tests."""
    return PoolsideGroup(
        uuid=uuid,
        name=name,
        kind=kind,
        body_of_water_uuid=body_of_water_uuid,
        body_of_water_type=body_of_water_type,
    )


def make_control(
    uuid: str,
    name: str,
    control_type: ControlType,
    group: PoolsideGroup = DEFAULT_GROUP,
    **raw: Any,
) -> PoolsideControl:
    """Build a PoolsideControl for tests."""
    return PoolsideControl(
        uuid=uuid, name=name, control_type=control_type, group=group, raw=raw
    )


class FakePoolsideClient:
    """A lightweight stand-in for PoolsideClient used by entity/platform tests."""

    def __init__(self, controller_uuid: str = TEST_CONTROLLER_UUID) -> None:
        """Set up the fake client with no status and no controls."""
        self.controller_uuid = controller_uuid
        self.site_uuid: str | None = TEST_SITE_UUID
        self.available = True
        self._status: dict[str, dict[str, Any]] = {}
        self._status_listeners: dict[str, list[Callable[[], None]]] = {}
        self._connection_listeners: list[Callable[[bool], None]] = []
        self._auth_failure_callback: Callable[[], None] | None = None
        self.async_connect = AsyncMock()
        self.async_disconnect = AsyncMock()
        self.async_get_control_layout = AsyncMock(return_value=(TEST_SITE, []))
        self.async_get_pool_devices = AsyncMock(return_value=[])
        self.async_set_desired_state = AsyncMock()

    def set_auth_failure_callback(self, callback: Callable[[], None]) -> None:
        """Store the auth failure callback for tests that want to trigger it."""
        self._auth_failure_callback = callback

    def get_status(self, control_uuid: str, field: str) -> Any:
        """Return the last known value of a named status field for a control."""
        return self._status.get(control_uuid, {}).get(field)

    @property
    def site_mode(self) -> Any:
        """Return the last reported site-wide Mode, mirroring PoolsideClient."""
        if self.site_uuid is None:
            return None
        return self.get_status(self.site_uuid, "Mode")

    def set_status(self, control_uuid: str, field: str, value: Any) -> None:
        """Set a status field and notify subscribers, mimicking a status push."""
        self._status.setdefault(control_uuid, {})[field] = value
        for listener in list(self._status_listeners.get(control_uuid, [])):
            listener()

    def set_connected(self, connected: bool) -> None:
        """Toggle overall connectivity and notify subscribers."""
        self.available = connected
        for listener in list(self._connection_listeners):
            listener(connected)

    def subscribe_status(
        self, control_uuid: str, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a status listener for a control."""
        listeners = self._status_listeners.setdefault(control_uuid, [])
        listeners.append(listener)

        def unsubscribe() -> None:
            listeners.remove(listener)

        return unsubscribe

    def subscribe_connection(
        self, listener: Callable[[bool], None]
    ) -> Callable[[], None]:
        """Register a connectivity listener."""
        self._connection_listeners.append(listener)

        def unsubscribe() -> None:
            self._connection_listeners.remove(listener)

        return unsubscribe


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock Poolside config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_CONTROLLER_UUID,
        title="Poolside",
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_CLIENT_NAME: TEST_CLIENT_NAME,
            CONF_CLIENT_PRIVATE_KEY: TEST_CLIENT_PRIVATE_KEY,
            CONF_CONTROLLER_PUBLIC_KEY: TEST_CONTROLLER_PUBLIC_KEY,
            CONF_CONTROLLER_UUID: TEST_CONTROLLER_UUID,
        },
    )


@pytest.fixture
def controls() -> list[PoolsideControl]:
    """Controls returned by Site.getControlLayout; override in test modules."""
    return []


@pytest.fixture
def pool_devices() -> list[PoolsideDevice]:
    """Devices returned by Site.getPoolDevices; override in test modules."""
    return []


@pytest.fixture
def fake_client(
    controls: list[PoolsideControl], pool_devices: list[PoolsideDevice]
) -> FakePoolsideClient:
    """Return a fresh fake Poolside client pre-loaded with `controls`."""
    client = FakePoolsideClient()
    client.async_get_control_layout.return_value = (TEST_SITE, controls)
    client.async_get_pool_devices.return_value = pool_devices
    return client


@pytest.fixture
def mock_poolside_client(
    fake_client: FakePoolsideClient,
) -> Generator[FakePoolsideClient]:
    """Patch PoolsideClient so async_setup_entry uses the fake client."""
    with patch(
        "homeassistant.components.poolside.PoolsideClient",
        return_value=fake_client,
    ):
        yield fake_client


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Set up the Poolside integration with the fake client."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
