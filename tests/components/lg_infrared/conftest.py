"""Common fixtures for the LG Infrared tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols import Command as InfraredCommand
import pytest

from homeassistant.components.infrared import (
    DATA_COMPONENT as INFRARED_DATA_COMPONENT,
    DOMAIN as INFRARED_DOMAIN,
    InfraredEntity,
)
from homeassistant.components.lg_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    LGDeviceType,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_INFRARED_ENTITY_ID = "infrared.test_ir_transmitter"


class MockInfraredEntity(InfraredEntity):
    """Mock infrared entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test IR transmitter"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock entity."""
        self._attr_unique_id = unique_id
        self.send_command_calls: list[InfraredCommand] = []

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Mock send command."""
        self.send_command_calls.append(command)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="LG TV via Test IR transmitter",
        data={
            CONF_DEVICE_TYPE: LGDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
        unique_id=f"lg_ir_tv_{MOCK_INFRARED_ENTITY_ID}",
    )


@pytest.fixture
def mock_infrared_entity() -> MockInfraredEntity:
    """Return a mock infrared entity."""
    return MockInfraredEntity("test_ir_transmitter")


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.MEDIA_PLAYER]


@pytest.fixture
def mock_make_lg_tv_command() -> Generator[None]:
    """Patch make_command to return the LGTVCode directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw NEC timings.
    """
    with patch(
        "homeassistant.components.lg_infrared.media_player.make_lg_tv_command",
        side_effect=lambda code, **kwargs: code,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
    mock_make_lg_tv_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the LG Infrared integration for testing."""
    assert await async_setup_component(hass, INFRARED_DOMAIN, {})
    await hass.async_block_till_done()

    infrared_component = hass.data[INFRARED_DATA_COMPONENT]
    await infrared_component.async_add_entities([mock_infrared_entity])

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lg_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
