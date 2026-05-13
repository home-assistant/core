"""Test configuration and fixtures for Imou integration."""

from collections.abc import AsyncGenerator, Generator, Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.imou.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .util import (
    CONFIG_ENTRY_DATA,
    create_mock_device_manager,
    new_imou_openapi_client_mock,
)

from tests.common import MockConfigEntry

PATCH_CONFIG_FLOW_IMOU_OPENAPI_CLIENT = (
    "homeassistant.components.imou.config_flow.ImouOpenApiClient"
)
PATCH_PACKAGE_IMOU_OPENAPI_CLIENT = "homeassistant.components.imou.ImouOpenApiClient"
PATCH_PACKAGE_IMOU_HA_DEVICE_MANAGER = (
    "homeassistant.components.imou.ImouHaDeviceManager"
)


@contextmanager
def imou_package_setup_patches(mock_device_manager: MagicMock) -> Iterator[None]:
    """Patch OpenAPI client and HA device manager where async_setup_entry resolves them."""
    with (
        patch(
            PATCH_PACKAGE_IMOU_OPENAPI_CLIENT,
            return_value=new_imou_openapi_client_mock(),
        ),
        patch(
            PATCH_PACKAGE_IMOU_HA_DEVICE_MANAGER,
            return_value=mock_device_manager,
        ),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Imou",
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA,
        unique_id=CONFIG_ENTRY_DATA["app_id"],
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_api_client() -> Generator[MagicMock]:
    """Create a mock API client used by the config flow."""
    with patch(
        PATCH_CONFIG_FLOW_IMOU_OPENAPI_CLIENT,
    ) as mock_client:
        mock_instance = new_imou_openapi_client_mock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry so config flow tests do not load the full integration."""
    with patch(
        "homeassistant.components.imou.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def imou_mock_devices(request: pytest.FixtureRequest) -> list:
    """Devices returned by ImouHaDeviceManager.async_get_devices (override via indirect)."""
    return getattr(request, "param", [])


@pytest.fixture
async def imou_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    imou_mock_devices: list,
) -> AsyncGenerator[MagicMock]:
    """Set up Imou with mocked pyimouapi clients; yields the device manager mock."""
    mock_dm = create_mock_device_manager()
    mock_dm.async_get_devices = AsyncMock(return_value=imou_mock_devices)
    with imou_package_setup_patches(mock_dm):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        try:
            yield mock_dm
        finally:
            if mock_config_entry.state is ConfigEntryState.LOADED:
                await hass.config_entries.async_unload(mock_config_entry.entry_id)
                await hass.async_block_till_done()
