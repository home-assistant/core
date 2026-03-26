"""Tests for SMLIGHT services."""

from unittest.mock import MagicMock

from pysmlight import Info
from pysmlight.exceptions import SmlightError
from pysmlight.models import BuzzerPayload
import pytest

from homeassistant.components.smlight.const import DOMAIN
from homeassistant.components.smlight.services import ATTR_TONE, SERVICE_PLAY_RTTTL
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .conftest import setup_integration

from tests.common import MockConfigEntry

MOCK_ULTIMA = Info(
    MAC="AA:BB:CC:DD:EE:FF",
    model="SLZB-Ultima3",
)

TEST_TONE = "smb:d=4,o=5,b=100:16e6,16e6"


async def test_play_rtttl_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test play_rtttl service."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA

    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    device_id = devices[0].id

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_RTTTL,
        {ATTR_DEVICE_ID: [device_id], ATTR_TONE: TEST_TONE},
        blocking=True,
    )

    mock_smlight_client.actions.buzzer.assert_called_once_with(
        BuzzerPayload(code=TEST_TONE)
    )


async def test_play_rtttl_service_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test play_rtttl service on unsupported model."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    device_id = devices[0].id

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_RTTTL,
            {ATTR_DEVICE_ID: [device_id], ATTR_TONE: TEST_TONE},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "not_supported_buzzer"

    mock_smlight_client.actions.buzzer.assert_not_called()


@pytest.mark.usefixtures("mock_smlight_client")
async def test_play_rtttl_service_no_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test play_rtttl service raises for unknown device."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_RTTTL,
            {ATTR_DEVICE_ID: ["non_existent_device_id"], ATTR_TONE: TEST_TONE},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_device_found"


async def test_play_rtttl_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test play_rtttl service handles api error."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    mock_smlight_client.actions.buzzer.side_effect = SmlightError("API fail")

    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    device_id = devices[0].id

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_RTTTL,
            {ATTR_DEVICE_ID: [device_id], ATTR_TONE: TEST_TONE},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "play_tone_failed"
    assert exc_info.value.translation_placeholders == {"error": "API fail"}
