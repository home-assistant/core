"""Common fixtures for the Samsung Infrared tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.samsung_infrared import PLATFORMS
from homeassistant.components.samsung_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    SamsungDeviceType,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID as MOCK_INFRARED_ENTITY_ID


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="Samsung TV via Test IR emitter",
        data={
            CONF_DEVICE_TYPE: SamsungDeviceType.TV,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
        unique_id=f"samsung_infrared_tv_{MOCK_INFRARED_ENTITY_ID}",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_make_samsung_tv_command() -> Generator[None]:
    """Patch SamsungTVCode.to_command to return the code directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw Samsung32 timings.
    """
    with patch(
        "infrared_protocols.codes.samsung.tv.SamsungTVCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity,
    mock_make_samsung_tv_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Samsung Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.samsung_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
