"""Common fixtures for the Amcrest tests."""

from collections.abc import AsyncGenerator, Generator
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.amcrest import PLATFORMS
from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.100"
TEST_PORT = 80
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"
TEST_SERIAL = "12345"
TEST_CONFIG_ENTRY_TITLE = f"Amcrest {TEST_SERIAL}"


def mock_async_property(
    api: MagicMock,
    name: str,
    *,
    return_value: Any = None,
    side_effect: type[BaseException] | BaseException | None = None,
) -> None:
    """Mock an Amcrest API property that is awaited."""

    async def _get_value() -> Any:
        if side_effect is not None:
            if isinstance(side_effect, type) and issubclass(side_effect, BaseException):
                raise side_effect
            raise side_effect
        return return_value

    setattr(type(api), name, property(lambda self: _get_value()))


def setup_mock_amcrest_checker(mock_class: MagicMock) -> MagicMock:
    """Configure a mocked AmcrestChecker for integration tests."""
    api = MagicMock()
    api.available = True
    api.available_flag = threading.Event()
    api.available_flag.set()
    api.get_base_url.return_value = f"http://{TEST_HOST}:{TEST_PORT}"
    mock_async_property(api, "async_current_time", return_value=None)
    mock_async_property(api, "async_serial_number", return_value=TEST_SERIAL)
    mock_async_property(api, "async_vendor_information", return_value="Amcrest")
    mock_async_property(api, "async_device_type", return_value="IP Camera")
    mock_async_property(api, "async_record_mode", return_value="Manual")
    mock_async_property(api, "async_day_night_color", return_value=0)
    mock_async_property(api, "async_ptz_presets_count", return_value=0)
    mock_async_property(
        api,
        "async_storage_all",
        return_value={"total": [0, "GB"], "used": [0, "GB"], "used_percent": "0"},
    )
    api.async_event_channels_happened = AsyncMock(return_value=False)
    api.async_privacy_config = AsyncMock(return_value="Enable=true")
    api.async_rtsp_url = AsyncMock(return_value="rtsp://example/stream")
    api.async_is_video_enabled = AsyncMock(return_value=True)
    api.async_is_motion_detector_on = AsyncMock(return_value=False)
    api.async_is_audio_enabled = AsyncMock(return_value=False)
    api.async_is_record_on_motion_detection = AsyncMock(return_value=False)
    api.async_command = AsyncMock(
        return_value=MagicMock(content=MagicMock(decode=MagicMock(return_value="true")))
    )
    mock_class.return_value = api
    return api


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.amcrest.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_CONFIG_ENTRY_TITLE,
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        unique_id=TEST_SERIAL,
    )


@pytest.fixture
async def loaded_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Return a loaded config entry with platforms set up."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.amcrest.AmcrestChecker") as mock_checker,
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        setup_mock_amcrest_checker(mock_checker)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry


@pytest.fixture
def mock_amcrest_api() -> Generator[MagicMock]:
    """Return a mocked AmcrestChecker."""
    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker",
    ) as mock_api_class:
        api = MagicMock()
        mock_async_property(api, "async_current_time", return_value=None)
        mock_async_property(api, "async_serial_number", return_value=TEST_SERIAL)
        mock_api_class.return_value = api
        yield mock_api_class


@pytest.fixture(autouse=True)
async def mock_patch_platforms() -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", PLATFORMS):
        yield
