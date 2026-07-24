"""bosch_shc session fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock bosch_shc config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )


@pytest.fixture
def mock_session(request: pytest.FixtureRequest) -> MagicMock:
    """Mock SHCSession with a happy-path SHCInformation.

    Override the reported update state via
    ``@pytest.mark.parametrize("mock_session", ["UPDATE_AVAILABLE"], indirect=True)``.
    """
    update_state = getattr(request, "param", "UP_TO_DATE")
    session = MagicMock()
    session.information.unique_id = "test-mac"
    session.information.updateState.name = update_state
    session.information.version = "2.0"
    return session
