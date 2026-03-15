"""The TIS Control integration conftest."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry to prevent the integration from fully loading."""
    with patch(
        "homeassistant.components.tis_control.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_tis_api() -> Generator[MagicMock]:
    """Mock the TISApi class."""
    with (
        patch("homeassistant.components.tis_control.TISApi") as mock_cls,
        patch(
            "homeassistant.components.tis_control.config_flow.TISApi", create=True
        ) as mock_flow_cls,
    ):
        instance = mock_cls.return_value
        mock_flow_cls.return_value = instance

        # Default async method mocks
        instance.connect = AsyncMock(return_value=True)
        instance.scan_devices = AsyncMock()
        instance.get_entities = AsyncMock(return_value=[])

        # Mock the infinite event generator for the background task
        async def _mock_consume_events():
            for _ in ():
                yield

        instance.consume_events = MagicMock(side_effect=_mock_consume_events)

        yield instance


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(
        title="CN11A1A00001",
        domain=DOMAIN,
        data={CONF_PORT: 6000},
        unique_id="CN11A1A00001",
    )
    entry.add_to_hass(hass)
    return entry
