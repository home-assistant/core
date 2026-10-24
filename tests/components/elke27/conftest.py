"""Fixtures for the Elke27 tests."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

from elke27_lib import AreaState, LinkKeys
import pytest

from homeassistant.components.elke27.const import (
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT

from . import build_snapshot

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for a linked panel."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Panel",
        unique_id="1234",
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_CLIENT_ID: "112233445566",
        },
    )


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock a connected Elke27 client."""
    with patch(
        "homeassistant.components.elke27.coordinator.Elke27Client", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.is_ready = True
        client.wait_ready.return_value = True
        client.async_set_zone_bypass.return_value = True
        client.async_arm_area.return_value = True
        client.async_disarm_area.return_value = True
        client.get_snapshot.return_value = build_snapshot(
            areas={1: AreaState(area_id=1, name="Area 1")}
        )

        def _subscribe(callback: Callable[[Any], None]) -> MagicMock:
            client.connection_callback = callback
            return MagicMock()

        def _subscribe_typed(callback: Callable[[Any], None]) -> MagicMock:
            client.event_callback = callback
            return MagicMock()

        client.subscribe.side_effect = _subscribe
        client.subscribe_typed.side_effect = _subscribe_typed
        yield client
