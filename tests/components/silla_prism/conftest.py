"""Fixtures for the Silla Prism tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.silla_prism.const import CONF_BASE_TOPIC, DOMAIN
from homeassistant.core import HomeAssistant

from .const import BASE_TOPIC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mocked config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Silla Prism",
        unique_id=BASE_TOPIC,
        data={CONF_BASE_TOPIC: BASE_TOPIC},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.silla_prism.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
