"""Test the Ubiquiti airOS buttons."""

from unittest.mock import AsyncMock

from airos.exceptions import AirOSDataMissingError, AirOSDeviceConnectionError
import pytest

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reboot_button_press_success(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that pressing the reboot button utilises the correct calls."""
    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    entity_id = "button.nanostation_5ac_ap_name_reboot_device"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{mock_config_entry.unique_id}_reboot"

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_airos_client.reboot.assert_awaited_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reboot_button_press_fail(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that pressing the reboot button utilises the correct calls."""
    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    entity_id = "button.nanostation_5ac_ap_name_reboot_device"
    mock_airos_client.reboot.return_value = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    mock_airos_client.reboot.assert_awaited_once()
    assert "failed to initiate" in caplog.text


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "exception",
    [
        AirOSDeviceConnectionError,
        AirOSDataMissingError,
    ],
)
async def test_reboot_button_press_exceptions(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reboot failure is handled gracefully."""
    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    entity_id = "button.nanostation_5ac_ap_name_reboot_device"

    mock_airos_client.login.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    mock_airos_client.reboot.assert_not_awaited()
    assert "Failed to send" in caplog.text

    mock_airos_client.login.side_effect = None
    mock_airos_client.reboot.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    mock_airos_client.reboot.assert_awaited_once()
    assert "Failed to send" in caplog.text

    mock_airos_client.reboot.side_effect = None

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_airos_client.reboot.assert_awaited()
