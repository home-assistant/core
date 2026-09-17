"""Tests for the diagnostics data provided by the Hot Spring integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


async def test_diagnostics_custom_topic(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics to ensure root_topic without MAC address is not redacted.

    This preserves diagnosing capabilities in case a spa model acts differently than expected.
    """
    coordinator = init_integration.runtime_data
    coordinator.data.info.root_topic = "customTopic"
    coordinator.data.info.hostname = "customHost"

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
