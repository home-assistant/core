"""Fixtures for Minecraft Server integration tests."""

import pytest

from homeassistant.components.minecraft_server.api import MinecraftServerType
from homeassistant.components.minecraft_server.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TYPE

from .const import TEST_ADDRESS, TEST_CONFIG_ENTRY_ID

from tests.common import MockConfigEntry


@pytest.fixture
def java_mock_config_entry() -> MockConfigEntry:
    """Create YouTube entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id=TEST_CONFIG_ENTRY_ID,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_ADDRESS: TEST_ADDRESS,
            CONF_TYPE: MinecraftServerType.JAVA_EDITION,
        },
        version=3,
    )


@pytest.fixture
def bedrock_mock_config_entry() -> MockConfigEntry:
    """Create YouTube entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id=TEST_CONFIG_ENTRY_ID,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_ADDRESS: TEST_ADDRESS,
            CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
        },
        version=3,
    )
