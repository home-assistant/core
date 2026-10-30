"""Common fixtures for the SilverCrest Infrared tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID

from homeassistant.components.silvercrest_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SilverCrestIrDeviceType,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.silvercrest_infrared.async_setup_entry",
        return_value=None,
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
                else SilverCrestIrDeviceType.SSVS85A1
            ),
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )


@pytest.fixture(name="infrared_codes")
def mock_infrared_code_to_command() -> Generator[None]:
    """Patch to_command to return the code directly.

    This allows tests to assert on the high-level code enum value
    rather than the raw Symphony timings.
    """
    with patch(
        "infrared_protocols.codes.silvercrest.fan.SilverCrestFanCode.to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ):
        yield
