"""Tests for Alexa Devices services."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.const import DOMAIN
from homeassistant.components.alexa_devices.services import (
    ATTR_INFO_SKILL,
    ATTR_SOUND,
    ATTR_TEXT_COMMAND,
    SERVICE_INFO_SKILL,
    SERVICE_SOUND_NOTIFICATION,
    SERVICE_TEXT_COMMAND,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_DEVICE_1_ID, TEST_DEVICE_1_SN

from tests.common import MockConfigEntry, mock_device_registry


async def test_setup_services(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup of Alexa Devices services."""
    await setup_integration(hass, mock_config_entry)

    assert (services := hass.services.async_services_for_domain(DOMAIN))
    assert SERVICE_TEXT_COMMAND in services
    assert SERVICE_SOUND_NOTIFICATION in services
    assert SERVICE_INFO_SKILL in services


async def test_info_skill_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test info skill service."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INFO_SKILL,
        {
            ATTR_INFO_SKILL: "tell_joke",
            ATTR_DEVICE_ID: device_entry.id,
        },
        blocking=True,
    )

    assert mock_amazon_devices_client.call_alexa_info_skill.call_count == 1
    assert mock_amazon_devices_client.call_alexa_info_skill.call_args == snapshot


async def test_send_sound_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send sound service."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SOUND_NOTIFICATION,
        {
            ATTR_SOUND: "bell_02",
            ATTR_DEVICE_ID: device_entry.id,
        },
        blocking=True,
    )

    assert mock_amazon_devices_client.call_alexa_sound.call_count == 1
    assert mock_amazon_devices_client.call_alexa_sound.call_args == snapshot


async def test_send_text_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send text service."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TEXT_COMMAND,
        {
            ATTR_TEXT_COMMAND: "Play B.B.C. radio on TuneIn",
            ATTR_DEVICE_ID: device_entry.id,
        },
        blocking=True,
    )

    assert mock_amazon_devices_client.call_alexa_text_command.call_count == 1
    assert mock_amazon_devices_client.call_alexa_text_command.call_args == snapshot


@pytest.mark.parametrize(
    ("sound", "device_id", "translation_key", "translation_placeholders"),
    [
        (
            "bell_02",
            "fake_device_id",
            "invalid_device_id",
            {"device_id": "fake_device_id"},
        ),
        (
            "wrong_sound_name",
            TEST_DEVICE_1_ID,
            "invalid_sound_value",
            {
                "sound": "wrong_sound_name",
            },
        ),
    ],
)
async def test_invalid_parameters(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    sound: str,
    device_id: str,
    translation_key: str,
    translation_placeholders: dict[str, str],
) -> None:
    """Test invalid service parameters."""

    device_entry = dr.DeviceEntry(
        id=TEST_DEVICE_1_ID, identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    mock_device_registry(
        hass,
        {device_entry.id: device_entry},
    )
    await setup_integration(hass, mock_config_entry)

    # Call Service
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SOUND_NOTIFICATION,
            {
                ATTR_SOUND: sound,
                ATTR_DEVICE_ID: device_id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == translation_placeholders


@pytest.mark.parametrize(
    ("info_skill", "device_id", "translation_key", "translation_placeholders"),
    [
        (
            "tell_joke",
            "fake_device_id",
            "invalid_device_id",
            {"device_id": "fake_device_id"},
        ),
        (
            "wrong_info_skill_name",
            TEST_DEVICE_1_ID,
            "invalid_info_skill_value",
            {
                "info_skill": "wrong_info_skill_name",
            },
        ),
    ],
)
async def test_invalid_info_skillparameters(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    info_skill: str,
    device_id: str,
    translation_key: str,
    translation_placeholders: dict[str, str],
) -> None:
    """Test invalid info skill service parameters."""

    device_entry = dr.DeviceEntry(
        id=TEST_DEVICE_1_ID, identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    mock_device_registry(
        hass,
        {device_entry.id: device_entry},
    )
    await setup_integration(hass, mock_config_entry)

    # Call Service
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INFO_SKILL,
            {
                ATTR_INFO_SKILL: info_skill,
                ATTR_DEVICE_ID: device_id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == translation_placeholders


async def test_config_entry_not_loaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not loaded."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    assert device_entry

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    # Call Service
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SOUND_NOTIFICATION,
            {
                ATTR_SOUND: "bell_02",
                ATTR_DEVICE_ID: device_entry.id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entry_not_loaded"
    assert exc_info.value.translation_placeholders == {"entry": mock_config_entry.title}


async def test_invalid_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test invalid config entry."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    assert device_entry

    device_entry.config_entries.add("non_existing_entry_id")
    await hass.async_block_till_done()

    # Call Service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SOUND_NOTIFICATION,
        {
            ATTR_SOUND: "bell_02",
            ATTR_DEVICE_ID: device_entry.id,
        },
        blocking=True,
    )
    # No exception should be raised
    assert mock_amazon_devices_client.call_alexa_sound.call_count == 1


async def test_missing_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing config entry."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
    )
    assert device_entry

    device_entry.config_entries.clear()

    # Call Service
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SOUND_NOTIFICATION,
            {
                ATTR_SOUND: "bell_02",
                ATTR_DEVICE_ID: device_entry.id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "config_entry_not_found"
    assert exc_info.value.translation_placeholders == {"device_id": device_entry.id}
