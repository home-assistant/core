"""Common fixtures for the rtl_433 tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyrtl_433.normalizer import NormalizedEvent
import pytest

from homeassistant.components.rtl_433.const import (
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SECURE,
    DOMAIN,
    MINOR_VERSION,
    VERSION,
)

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.50"
MOCK_PORT = 8433
MOCK_PATH = "/ws"
MOCK_UNIQUE_ID = f"hub:{MOCK_HOST}:{MOCK_PORT}"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked rtl_433 hub config entry at the contract's schema version."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"rtl_433 ({MOCK_HOST})",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PATH: MOCK_PATH,
            CONF_SECURE: False,
        },
        unique_id=MOCK_UNIQUE_ID,
        version=VERSION,
        minor_version=MINOR_VERSION,
        entry_id="01JRTL433HUBAAAAAAAAAAAAAA",
    )


@pytest.fixture
def mock_rtl433_client() -> Generator[MagicMock]:
    """Mock the pyrtl_433 ``Rtl433Client`` used by the coordinator.

    The coordinator (and, via it, the config flow) is the sole importer of the
    client, so patching it there covers both the setup path and
    ``validate_connection`` (test-before-configure). The mocked instance reports
    as immediately connected so ``test-before-setup`` succeeds without a server.
    """
    with patch(
        "homeassistant.components.rtl_433.coordinator.Rtl433Client",
        autospec=True,
    ) as mock_client:
        instance = mock_client.return_value
        instance.connected = True
        instance.ws_url = f"ws://{MOCK_HOST}:{MOCK_PORT}{MOCK_PATH}"
        # ``validate_connection`` is a staticmethod on the class; the config flow
        # calls it on the class, so stub it there. Truthy return == reachable.
        mock_client.validate_connection = AsyncMock(return_value=True)
        yield mock_client


@pytest.fixture
def mock_event() -> NormalizedEvent:
    """Return a normalized rtl_433 event for a temperature/humidity sensor."""
    return NormalizedEvent(
        device_key="Acurite-606TX-42",
        model="Acurite-606TX",
        identity={"model": "Acurite-606TX", "id": 42},
        fields={"temperature_C": 21.5, "battery_ok": 1},
    )
