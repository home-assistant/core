"""Common fixtures for the INDI Allsky tests."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioindiallsky import ExposureData
import pytest

from homeassistant.components.indi_allsky.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(autouse=True)
def mock_system_random() -> Generator[None]:
    """Mock random.SystemRandom.getrandbits to produce deterministic camera access tokens."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.indi_allsky.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_indi_allsky_client() -> Generator[AsyncMock]:
    """Mock the third-party aioindiallsky client globally across coordinator and config flow."""
    callbacks: dict[str, list[Callable[..., Any]]] = {}

    def register_callback(
        event_type: str, callback: Callable[..., Any]
    ) -> Callable[[], None]:
        callbacks.setdefault(event_type, []).append(callback)
        return lambda: callbacks[event_type].remove(callback)

    with (
        patch(
            "homeassistant.components.indi_allsky.coordinator.IndiAllSkyClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.indi_allsky.config_flow.IndiAllSkyClient",
            new=mock_client,
        ),
    ):
        client_instance = mock_client.return_value
        client_instance.fetch_image = AsyncMock(return_value=b"fake_jpeg_data")
        client_instance.connect = AsyncMock()
        client_instance.listen = AsyncMock()
        client_instance.disconnect = AsyncMock()
        client_instance.is_connected = False
        client_instance.register_callback = MagicMock(side_effect=register_callback)
        client_instance.callbacks = callbacks
        yield client_instance


@pytest.fixture
def mock_exposure_data() -> ExposureData:
    """Fixture to provide sample ExposureData from fixture JSON."""
    raw_data = load_json_object_fixture("exposure_complete.json", DOMAIN)
    return ExposureData.from_dict(raw_data)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Fixture to cleanly create an INDI Allsky configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INDI Allsky",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
        entry_id="1234567890abcdef1234567890abcdef",
    )
