"""Common fixtures for the Sleep as Android tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sleep_as_android.const import DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sleep_as_android.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Sleep as Android configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sleep as Android",
        data={
            "cloudhook": False,
            CONF_WEBHOOK_ID: "webhook_id",
        },
        entry_id="01JRD840SAZ55DGXBD78PTQ4EF",
    )
