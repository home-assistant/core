"""Test the SFR Box sensors."""
from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import check_device_registry, check_entities
from .const import EXPECTED_ENTITIES

from tests.common import mock_device_registry, mock_registry

pytestmark = pytest.mark.usefixtures("system_get_info", "dsl_get_info")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None, None, None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


async def test_binary_sensors(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test for SFR Box binary sensors."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    check_device_registry(device_registry, EXPECTED_ENTITIES["expected_device"])

    expected_entities = EXPECTED_ENTITIES[Platform.BINARY_SENSOR]
    assert len(entity_registry.entities) == len(expected_entities)

    check_entities(hass, entity_registry, expected_entities)
