"""Common fixtures for the SilverCrest Infrared tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.silvercrest_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SilverCrestIrDeviceType,
)

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.silvercrest_infrared.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Misting fan via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: (
                request.param
                if hasattr(request, "param")
                else SilverCrestIrDeviceType.MISTING_FAN
            ),
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
