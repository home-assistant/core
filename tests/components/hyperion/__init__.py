"""Tests for the Hyperion component."""

import logging
from typing import Optional

from asynctest import CoroutineMock, Mock, patch
from hyperion import const

from homeassistant.components.hyperion.const import CONF_PRIORITY, DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_HOST = "test"
TEST_PORT = const.DEFAULT_PORT_JSON + 1
TEST_PORT_UI = const.DEFAULT_PORT_UI + 1
TEST_INSTANCE = 1
TEST_SERVER_ID = "f9aab089-f85a-55cf-b7c1-222a72faebe9"
TEST_PRIORITY = 180
TEST_YAML_NAME = f"{TEST_HOST}_{TEST_PORT}_{TEST_INSTANCE}"
TEST_YAML_ENTITY_ID = f"{LIGHT_DOMAIN}.{TEST_YAML_NAME}"
TEST_ENTITY_ID_1 = "light.test_instance_1"
TEST_ENTITY_ID_2 = "light.test_instance_2"
TEST_ENTITY_ID_3 = "light.test_instance_3"

TEST_TOKEN = "sekr1t"
TEST_HYPERION_URL = f"http://{TEST_HOST}:{const.DEFAULT_PORT_UI}"
TEST_CONFIG_ENTRY_ID = "74565ad414754616000674c87bdc876c"
TEST_CONFIG_ENTRY_OPTIONS = {CONF_PRIORITY: TEST_PRIORITY}

TEST_INSTANCE_1 = {"friendly_name": "Test instance 1", "instance": 1, "running": True}
TEST_INSTANCE_2 = {"friendly_name": "Test instance 2", "instance": 2, "running": True}
TEST_INSTANCE_3 = {"friendly_name": "Test instance 3", "instance": 3, "running": True}

_LOGGER = logging.getLogger(__name__)


class AsyncContextManagerMock(Mock):
    """An async context manager mock for Hyperion."""

    async def __aenter__(self) -> Optional["AsyncContextManagerMock"]:
        """Enter context manager and connect the client."""
        result = await self.async_client_connect()
        return self if result else None

    async def __aexit__(self, exc_type, exc, traceback):
        """Leave context manager and disconnect the client."""
        await self.async_client_disconnect()


def create_mock_client():
    """Create a mock Hyperion client."""
    mock_client = AsyncContextManagerMock()
    # pylint: disable=attribute-defined-outside-init
    mock_client.async_client_connect = CoroutineMock(return_value=True)
    mock_client.async_client_disconnect = CoroutineMock(return_value=True)
    mock_client.async_is_auth_required = CoroutineMock(
        return_value={
            "command": "authorize-tokenRequired",
            "info": {"required": False},
            "success": True,
            "tan": 1,
        }
    )
    mock_client.async_id = CoroutineMock(return_value=TEST_SERVER_ID)
    mock_client.adjustment = None
    mock_client.effects = None
    mock_client.instances = [
        {"friendly_name": "Test instance 1", "instance": 0, "running": True}
    ]

    return mock_client


def add_test_config_entry(hass):
    """Add a test config entry."""
    config_entry = MockConfigEntry(
        entry_id=TEST_CONFIG_ENTRY_ID,
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
        },
        title=f"Hyperion {TEST_SERVER_ID}",
        unique_id=TEST_SERVER_ID,
        options=TEST_CONFIG_ENTRY_OPTIONS,
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def setup_test_config_entry(hass, client=None):
    """Add a test Hyperion entity to hass."""
    assert await async_setup_component(hass, DOMAIN, {})
    config_entry = add_test_config_entry(hass)

    client = client or create_mock_client()
    # pylint: disable=attribute-defined-outside-init
    client.instances = [TEST_INSTANCE_1]

    with patch("hyperion.client.HyperionClient", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry
