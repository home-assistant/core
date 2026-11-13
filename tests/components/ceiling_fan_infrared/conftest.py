"""Common fixtures for the Ceiling Fan Infrared tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID

from homeassistant.components.ceiling_fan_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ceiling_fan_infrared.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Ceiling fan via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )


@pytest.fixture(name="infrared_codes")
def mock_infrared_code_to_command() -> Generator[None]:
    """Patch to_command to return the code directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw NEC timings.
    """
    with patch(
        "infrared_protocols.codes.generic.ceiling_fan.GenericCeilingFanCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield
