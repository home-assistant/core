"""Tests for the Imou coordinator."""

from unittest.mock import MagicMock

from pyimouapi.exceptions import ImouException
import pytest

from homeassistant.components.imou.const import DOMAIN
from homeassistant.components.imou.coordinator import ImouDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import default_mock_devices

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
) -> ImouDataUpdateCoordinator:
    """Return a coordinator backed by the shared Imou test mocks."""
    mock_config_entry.add_to_hass(hass)
    return ImouDataUpdateCoordinator(
        hass, mock_imou_ha_device_manager, mock_config_entry
    )


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        (TimeoutError("timeout"), "update_timeout"),
        (ImouException("cloud failure"), "fetch_devices_failed"),
    ],
)
async def test_coordinator_fetch_devices_update_failed(
    coordinator: ImouDataUpdateCoordinator,
    mock_imou_ha_device_manager: MagicMock,
    side_effect: Exception,
    translation_key: str,
) -> None:
    """Listing devices raises a translatable UpdateFailed."""
    mock_imou_ha_device_manager.async_get_devices.side_effect = side_effect

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        (TimeoutError("timeout"), "update_timeout"),
        (ImouException("cloud failure"), "update_devices_failed"),
    ],
)
async def test_coordinator_update_devices_status_update_failed(
    coordinator: ImouDataUpdateCoordinator,
    mock_imou_ha_device_manager: MagicMock,
    side_effect: Exception,
    translation_key: str,
) -> None:
    """Refreshing device status raises a translatable UpdateFailed."""
    mock_imou_ha_device_manager.async_get_devices.return_value = default_mock_devices()
    mock_imou_ha_device_manager.async_update_devices_status.side_effect = side_effect

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
