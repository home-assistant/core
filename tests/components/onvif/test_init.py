"""Tests for the ONVIF integration __init__ module."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FIRMWARE_VERSION,
    HOST,
    MAC,
    MANUFACTURER,
    MODEL,
    NAME,
    PASSWORD,
    PORT,
    SERIAL_NUMBER,
    USERNAME,
    setup_mock_device,
    setup_mock_onvif_camera,
)

from tests.common import MockConfigEntry


async def test_migrate_camera_entities_unique_ids(hass: HomeAssistant) -> None:
    """Test that camera entities unique ids get migrated properly."""
    config_entry = MockConfigEntry(domain="onvif", unique_id=MAC)
    config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    entity_with_only_mac = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=MAC,
        config_entry=config_entry,
    )
    entity_with_index = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}_1",
        config_entry=config_entry,
    )
    # This one should not be migrated (different domain)
    entity_sensor = entity_registry.async_get_or_create(
        domain="sensor",
        platform="onvif",
        unique_id=MAC,
        config_entry=config_entry,
    )
    # This one should not be migrated (already migrated)
    entity_migrated = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}#profile_token_2",
        config_entry=config_entry,
    )
    # Unparsable index
    entity_unparsable_index = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}_a",
        config_entry=config_entry,
    )
    # Unexisting index
    entity_unexisting_index = entity_registry.async_get_or_create(
        domain="camera",
        platform="onvif",
        unique_id=f"{MAC}_9",
        config_entry=config_entry,
    )

    with patch("homeassistant.components.onvif.ONVIFDevice") as mock_device:
        setup_mock_device(
            mock_device,
            capabilities=None,
            profiles=[
                MagicMock(token="profile_token_0"),
                MagicMock(token="profile_token_1"),
                MagicMock(token="profile_token_2"),
            ],
        )
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_with_only_mac = entity_registry.async_get(entity_with_only_mac.entity_id)
    entity_with_index = entity_registry.async_get(entity_with_index.entity_id)
    entity_sensor = entity_registry.async_get(entity_sensor.entity_id)
    entity_migrated = entity_registry.async_get(entity_migrated.entity_id)

    assert entity_with_only_mac is not None
    assert entity_with_only_mac.unique_id == f"{MAC}#profile_token_0"

    assert entity_with_index is not None
    assert entity_with_index.unique_id == f"{MAC}#profile_token_1"

    # Make sure the sensor entity is unchanged
    assert entity_sensor is not None
    assert entity_sensor.unique_id == MAC

    # Make sure the already migrated entity is unchanged
    assert entity_migrated is not None
    assert entity_migrated.unique_id == f"{MAC}#profile_token_2"

    # Make sure the unparsable index entity is unchanged
    assert entity_unparsable_index is not None
    assert entity_unparsable_index.unique_id == f"{MAC}_a"

    # Make sure the unexisting index entity is unchanged
    assert entity_unexisting_index is not None
    assert entity_unexisting_index.unique_id == f"{MAC}_9"


def _setup_full_onvif_camera_mocks(mock_onvif_camera_cls: MagicMock) -> None:
    """Configure the patched ONVIFCamera class for a full integration setup.

    Builds on the shared ``setup_mock_onvif_camera`` helper with the extra
    mocks required for ``ONVIFDevice.async_setup`` to complete, so the config
    entry can be set up against a real ``ONVIFDevice`` with only the onvif
    library mocked.
    """
    setup_mock_onvif_camera(mock_onvif_camera_cls)

    media_service = MagicMock()
    media_service.GetServiceCapabilities = AsyncMock(
        return_value=SimpleNamespace(SnapshotUri=False)
    )
    media_service.GetProfiles = AsyncMock(
        return_value=[
            SimpleNamespace(
                token="profile_token",
                Name="MainStream",
                VideoEncoderConfiguration=SimpleNamespace(
                    Resolution=SimpleNamespace(Width=1920, Height=1080),
                    Encoding="H264",
                ),
                VideoSourceConfiguration=MagicMock(),
                PTZConfiguration=MagicMock(),
            )
        ]
    )
    mock_onvif_camera_cls.create_media_service = AsyncMock(return_value=media_service)

    ptz_service = MagicMock()
    ptz_service.GetPresets = AsyncMock(return_value=[])
    mock_onvif_camera_cls.create_ptz_service = AsyncMock(return_value=ptz_service)
    mock_onvif_camera_cls.create_imaging_service = AsyncMock(return_value=MagicMock())
    mock_onvif_camera_cls.create_pullpoint_manager = AsyncMock(return_value=MagicMock())
    mock_onvif_camera_cls.get_snapshot = AsyncMock(return_value=False)
    mock_onvif_camera_cls.get_capabilities = AsyncMock(
        return_value={
            "Media": {"XAddr": "http://media"},
            "PTZ": {"XAddr": "http://ptz"},
            "Imaging": {"XAddr": "http://imaging"},
            "Events": {
                "XAddr": None,
                "WSPullPointSupport": False,
                "WSSubscriptionPolicySupport": False,
            },
        }
    )

    devicemgmt = mock_onvif_camera_cls.create_devicemgmt_service.return_value
    devicemgmt.GetSystemDateAndTime = AsyncMock(return_value=None)
    devicemgmt.GetDeviceInformation = AsyncMock(
        return_value=SimpleNamespace(
            Manufacturer=MANUFACTURER,
            Model=MODEL,
            FirmwareVersion=FIRMWARE_VERSION,
            SerialNumber=SERIAL_NUMBER,
        )
    )


async def test_setup_entry_with_real_device(hass: HomeAssistant) -> None:
    """Test setting up the config entry against a real ONVIFDevice.

    The onvif library is mocked while ``ONVIFDevice`` itself is real, so the
    full ``async_setup_entry`` flow is exercised. The other ONVIF tests mock
    ``ONVIFDevice`` entirely and do not cover this path.
    """
    entry = MockConfigEntry(
        domain="onvif",
        title=NAME,
        unique_id=MAC,
        data={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onvif.device.ONVIFCamera"
        ) as mock_onvif_camera_cls,
        patch(
            "homeassistant.components.onvif.device.ONVIFDevice.async_start_events",
            new=AsyncMock(return_value=False),
        ),
    ):
        _setup_full_onvif_camera_mocks(mock_onvif_camera_cls)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
