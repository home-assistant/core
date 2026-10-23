"""Common fixtures for the NAD Infrared tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.nad_infrared import PLATFORMS
from homeassistant.components.nad_infrared.codes import (
    NADAmplifierCode,
    NADCassetteCode,
    NADCDCode,
)
from homeassistant.components.nad_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DEVICE_NAMES,
    DOMAIN,
    NADDeviceType,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def device_type(request: pytest.FixtureRequest) -> NADDeviceType:
    """Return the NAD device type to use for the config entry.

    Override with ``@pytest.mark.parametrize("device_type", [...], indirect=True)``.
    """
    return getattr(request, "param", NADDeviceType.RECEIVER)


@pytest.fixture
def mock_config_entry(device_type: NADDeviceType) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title=DEVICE_NAMES[device_type],
        data={
            CONF_DEVICE_TYPE: device_type,
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        },
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_nad_to_command() -> Generator[MagicMock]:
    """Patch ``to_command`` on the NAD code enums to return the code itself.

    This lets tests assert on the code enum value rather than on raw timings.
    """
    with (
        patch.object(
            NADAmplifierCode, "to_command", autospec=True, side_effect=lambda self: self
        ) as mock,
        patch.object(
            NADCDCode, "to_command", autospec=True, side_effect=lambda self: self
        ),
        patch.object(
            NADCassetteCode, "to_command", autospec=True, side_effect=lambda self: self
        ),
    ):
        yield mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_nad_to_command: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the NAD Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.nad_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
