"""Common fixtures for the Dyson Infrared tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.dyson_infrared import PLATFORMS
from homeassistant.components.dyson_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID as MOCK_INFRARED_ENTITY_ID


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000001",
        title="Dyson Fan via Test IR emitter",
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.FAN,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
        unique_id=f"dyson_infrared_fan_{MOCK_INFRARED_ENTITY_ID}",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_make_dyson_cool_command() -> Generator[None]:
    """Patch DysonCoolCode.to_command to return the code directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw Dyson 15-bit timings.
    """
    with patch(
        "infrared_protocols.codes.dyson.cool.DysonCoolCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield


@pytest.fixture
def mock_speed_sleep() -> Generator[None]:
    """Skip the inter-command delay used when stepping fan speed."""
    with patch("homeassistant.components.dyson_infrared.fan.asyncio.sleep"):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity,
    mock_make_dyson_cool_command: None,
    mock_speed_sleep: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Dyson Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.dyson_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def fan_entity_id(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> str:
    """Return the entity_id of the Dyson fan entity created for the test entry."""
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    assert len(entries) == 1
    return entries[0].entity_id
