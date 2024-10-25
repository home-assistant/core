"""Smarty tests configuration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.smarty import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override integration setup."""
    with patch(
        "homeassistant.components.smarty.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_smarty() -> Generator[AsyncMock]:
    """Mock a Smarty client."""
    with (
        patch(
            "homeassistant.components.smarty.coordinator.Smarty",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.smarty.config_flow.Smarty",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.update.return_value = True
        client.fan_speed = 100
        client.warning = False
        client.alarm = False
        client.boost = False
        client.supply_air_temperature = 20
        client.extract_air_temperature = 23
        client.outdoor_air_temperature = 24
        client.supply_fan_speed = 66
        client.extract_fan_speed = 100
        client.filter_timer = 31
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.0.2"},
        entry_id="01JAZ5DPW8C62D620DGYNG2R8H",
    )
