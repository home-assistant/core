"""Common fixtures for the LG Infrared tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.lg_infrared import PLATFORMS
from homeassistant.components.lg_infrared.config_flow import DEVICE_TYPE_NAMES
from homeassistant.components.lg_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LGDeviceType,
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

ENTRY_ID = "01JTEST0000000000000000000"


@pytest.fixture
def device_type() -> LGDeviceType:
    """Return the device type of the config entry."""
    return LGDeviceType.TV


@pytest.fixture
def hvac_modes() -> list[HVACMode]:
    """Return the HVAC modes configured on an AC config entry."""
    return [HVACMode.COOL, HVACMode.DRY]


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return True


@pytest.fixture
def extra_entry_data(
    device_type: LGDeviceType, hvac_modes: list[HVACMode]
) -> dict[str, Any]:
    """Return the device type specific config entry data."""
    return {
        LGDeviceType.TV: {},
        LGDeviceType.AC: {CONF_HVAC_MODES: hvac_modes},
    }[device_type]


@pytest.fixture
def mock_config_entry(
    device_type: LGDeviceType,
    extra_entry_data: dict[str, Any],
    has_receiver: bool,
) -> MockConfigEntry:
    """Return a mock config entry for the configured device type."""
    data: dict[str, Any] = {
        CONF_DEVICE_TYPE: device_type,
        CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        **extra_entry_data,
    }
    if has_receiver:
        data[CONF_INFRARED_RECEIVER_ENTITY_ID] = MOCK_INFRARED_RECEIVER_ENTITY_ID

    device_name = DEVICE_TYPE_NAMES[device_type]
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title=f"LG {device_name} via Test IR emitter",
        data=data,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_lg_tv_code_to_command() -> Generator[None]:
    """Patch LGTVCode.to_command to return the LGTVCode directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw NEC timings.
    """
    with patch(
        "infrared_protocols.codes.lg.tv.LGTVCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    mock_lg_tv_code_to_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the LG Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lg_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
