"""Tests for the Advantage Air component."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_SYSTEM_DATA = load_json_object_fixture("getSystemData.json", DOMAIN)
TEST_SET_RESPONSE = None

USER_INPUT = {
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: 2025,
}

TEST_SYSTEM_URL = (
    f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/getSystemData"
)
TEST_SET_URL = f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/setAircon"
TEST_SET_LIGHT_URL = (
    f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/setLights"
)
TEST_SET_THING_URL = (
    f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/setThings"
)


def patch_get(return_value=TEST_SYSTEM_DATA, side_effect=None):
    """Patch the Advantage Air async_get method."""
    return patch(
        "homeassistant.components.advantage_air.advantage_air.async_get",
        new=AsyncMock(return_value=return_value, side_effect=side_effect),
    )


def patch_update(return_value=True, side_effect=None):
    """Patch the Advantage Air async_set method."""
    return patch(
        "homeassistant.components.advantage_air.advantage_air._endpoint.async_update",
        new=AsyncMock(return_value=return_value, side_effect=side_effect),
    )


async def add_mock_config(
    hass: HomeAssistant, platforms: list[Platform] | None = None
) -> MockConfigEntry:
    """Create a fake Advantage Air Config Entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test entry",
        unique_id="0123456",
        data=USER_INPUT,
    )

    entry.add_to_hass(hass)
    if platforms is None:
        await hass.config_entries.async_setup(entry.entry_id)
    else:
        with patch("homeassistant.components.advantage_air.PLATFORMS", platforms):
            await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def assert_entities(
    hass: HomeAssistant,
    entry_id: str,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all entities match their snapshot."""

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")
