"""Common fixtures for the Prana tests."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.prana.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create Prana mock config entry."""
    device_info_data = load_json_object_fixture("device_info.json", DOMAIN)
    device_info_obj = SimpleNamespace(**device_info_data)
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=device_info_obj.manufactureId,
        entry_id="0123456789abcdef0123456789abcdef",
        title=device_info_obj.label,
        data={
            CONF_HOST: "127.0.0.1",
        },
    )


@pytest.fixture
def mock_prana_api() -> Generator[AsyncMock]:
    """Mock the Prana API client used by the integration."""
    with (
        patch(
            "homeassistant.components.prana.config_flow.PranaLocalApiClient",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.prana.coordinator.PranaLocalApiClient",
            mock_api_class,
        ),
    ):
        device_info_data = load_json_object_fixture("device_info.json", DOMAIN)
        state_data = load_json_object_fixture("state.json", DOMAIN)

        device_info_obj = SimpleNamespace(**device_info_data)
        state_obj = SimpleNamespace(**state_data)

        mock_api_class.return_value.get_device_info = AsyncMock(
            return_value=device_info_obj
        )
        mock_api_class.return_value.get_state = AsyncMock(return_value=state_obj)

        yield mock_api_class.return_value
