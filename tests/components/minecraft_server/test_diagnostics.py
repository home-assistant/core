"""Tests for Minecraft Server diagnostics."""
import json
from unittest.mock import patch

from mcstatus import BedrockServer, JavaServer

from homeassistant.components.minecraft_server.api import MinecraftServerType
from homeassistant.components.minecraft_server.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import (
    TEST_ADDRESS,
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics_java(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test fetching of the Java Edition config entry diagnostics."""

    # Create and add mock entry.
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id="01234567890123456789012345678901",
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_ADDRESS: TEST_ADDRESS,
            CONF_TYPE: MinecraftServerType.JAVA_EDITION,
        },
        version=3,
    )
    mock_config_entry_id = mock_config_entry.entry_id
    mock_config_entry.add_to_hass(hass)

    # Setup mock entry.
    with patch(
        "mcstatus.server.JavaServer.lookup",
        side_effect=None,
        return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        "mcstatus.server.JavaServer.async_status",
        return_value=TEST_JAVA_STATUS_RESPONSE,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry_id)
        await hass.async_block_till_done()

    # Test diagnostics.
    diagnostics_fixture = json.loads(
        load_fixture("diagnostics_java_edition.json", DOMAIN)
    )
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == diagnostics_fixture
    )


async def test_config_entry_diagnostics_bedrock(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test fetching of the Bedrock Edition config entry diagnostics."""

    # Create and add mock entry.
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id="01234567890123456789012345678901",
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_ADDRESS: TEST_ADDRESS,
            CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
        },
        version=3,
    )
    mock_config_entry_id = mock_config_entry.entry_id
    mock_config_entry.add_to_hass(hass)

    # Setup mock entry.
    with patch(
        "mcstatus.server.BedrockServer.lookup",
        side_effect=None,
        return_value=BedrockServer(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        "mcstatus.server.BedrockServer.async_status",
        return_value=TEST_BEDROCK_STATUS_RESPONSE,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry_id)
        await hass.async_block_till_done()

    # Test diagnostics.
    diagnostics_fixture = json.loads(
        load_fixture("diagnostics_bedrock_edition.json", DOMAIN)
    )
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == diagnostics_fixture
    )
