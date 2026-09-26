"""Common fixtures for the Dyson Infrared tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.dyson_infrared.const import (
    CONF_COMMAND_STEP_DELAY,
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)
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
            CONF_COMMAND_STEP_DELAY: 0,
        },
        unique_id=f"fan_{MOCK_INFRARED_ENTITY_ID}",
    )


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
def mock_make_dyson_am09_command() -> Generator[None]:
    """Patch DysonAm09Code.to_command to return the code directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw Dyson 15-bit timings.
    """
    with patch(
        "infrared_protocols.codes.dyson.am09.DysonAm09Code.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity,
    mock_make_dyson_cool_command: None,
    mock_make_dyson_am09_command: None,
) -> MockConfigEntry:
    """Set up the Dyson Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

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


@pytest.fixture
def climate_entity_id(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> str:
    """Return the entity_id of the Dyson climate entity created for the test entry."""
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    assert len(entries) == 1
    return entries[0].entity_id
