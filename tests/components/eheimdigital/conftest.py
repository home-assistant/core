"""Configurations for the EHEIM Digital tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from eheimdigital.hub import EheimDigitalHub
import pytest

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "eheimdigital"})


@pytest.fixture
def eheimdigital_hub_mock() -> Generator[AsyncMock]:
    """Mock eheimdigital hub."""
    with (
        patch(
            "homeassistant.components.eheimdigital.coordinator.EheimDigitalHub",
            spec=EheimDigitalHub,
        ) as mock,
        patch(
            "homeassistant.components.eheimdigital.config_flow.EheimDigitalHub",
            new=mock,
        ),
    ):
        yield mock
