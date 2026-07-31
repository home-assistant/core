"""Test the initialization of Yardian."""

from unittest.mock import AsyncMock

import pytest
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        (NotAuthorizedException, ConfigEntryState.SETUP_ERROR),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (NetworkException, ConfigEntryState.SETUP_RETRY),
        (Exception, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_unauthorized(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test setup when unauthorized."""
    mock_yardian_client.fetch_device_state.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is entry_state


async def test_zone_device_via_device(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that zone child devices link to the main device via via_device_id."""
    await setup_integration(hass, mock_config_entry)

    main_device = device_registry.async_get_device(identifiers={(DOMAIN, "yid123")})
    zone_device = device_registry.async_get_device(identifiers={(DOMAIN, "yid123_0")})

    assert main_device is not None
    assert zone_device is not None
    assert zone_device.via_device_id == main_device.id
