"""Common fixtures for the OSRAM infrared tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.osram_infrared import PLATFORMS
from homeassistant.components.osram_infrared.const import (
    CONF_IR_EMITTER_ENTITY_ID,
    CONF_IR_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID as MOCK_INFRARED_RECEIVER_ENTITY_ID,
)
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock OSRAM infrared config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="OSRAM light via Test IR emitter",
        data={CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )


@pytest.fixture
def mock_config_entry_with_receiver() -> MockConfigEntry:
    """Return a mock OSRAM infrared config entry with a receiver."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="OSRAM light via Test IR emitter",
        data={
            CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_IR_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
        },
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_osram_light_code_to_command() -> Generator[None]:
    """Patch OsramLightCode.to_command to return the OsramLightCode directly.

    This allows tests to assert on the high-level code enum value rather than the
    raw NEC command timings.
    """
    with patch(
        "infrared_protocols.codes.osram.light.OsramLightCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_osram_light_code_to_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the OSRAM Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.osram_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def init_integration_with_receiver(
    hass: HomeAssistant,
    mock_config_entry_with_receiver: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    mock_osram_light_code_to_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the OSRAM Infrared integration for testing."""
    mock_config_entry_with_receiver.add_to_hass(hass)

    with patch("homeassistant.components.osram_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry_with_receiver.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry_with_receiver
