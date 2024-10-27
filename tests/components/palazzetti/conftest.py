"""Fixtures for Palazzetti integration tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.palazzetti.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="palazzetti",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "11:22:33:44:55:66",
        },
        unique_id="11:22:33:44:55:66",
    )


@pytest.fixture
def mock_palazzetti_client():
    """Return a mocked PalazzettiClient."""
    with (
        patch(
            "homeassistant.components.palazzetti.coordinator.PalazzettiClient",
            AsyncMock,
        ) as mock_client,
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient",
            new=mock_client,
        ),
    ):
        data = json.loads(load_fixture("palazzetti_client_example1.json", DOMAIN))
        for k, v in data.items():
            setattr(mock_client, k, v)
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.update_state = AsyncMock(return_value=True)
        mock_client.set_on = AsyncMock(return_value=True)
        mock_client.set_target_temperature = AsyncMock(return_value=True)
        mock_client.set_fan_speed = AsyncMock(return_value=True)
        mock_client.set_fan_silent = AsyncMock(return_value=True)
        mock_client.set_fan_high = AsyncMock(return_value=True)
        mock_client.set_fan_auto = AsyncMock(return_value=True)
        yield mock_client


@pytest.fixture(params=["example1", "example2"])
def palazzetti_devices(
    mock_palazzetti_client: AsyncMock, request: pytest.FixtureRequest
) -> Generator[AsyncMock]:
    """Return a list of AirGradient devices."""
    data = json.loads(load_fixture(f"palazzetti_client_{request.param}.json", DOMAIN))
    for k, v in data.items():
        setattr(mock_palazzetti_client, k, v)

    return mock_palazzetti_client
