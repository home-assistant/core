"""Tests for the ONVIF integration __init__ module."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from homeassistant.components.onvif.const import CONF_SNAPSHOT_AUTH, DOMAIN
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
    HOST,
    MAC,
    NAME,
    PASSWORD,
    PORT,
    USERNAME,
    setup_mock_device,
    setup_mock_onvif_camera,
)

from tests.common import MockConfigEntry


async def test_migrate_camera_entities_unique_ids(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that camera entities unique ids get migrated properly."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id=MAC)
    config_entry.add_to_hass(hass)

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


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
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

    with patch(
        "homeassistant.components.onvif.device.ONVIFCamera"
    ) as mock_onvif_camera_cls:
        setup_mock_onvif_camera(mock_onvif_camera_cls, with_full_setup=True)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_onvif_camera_cls.assert_called_once()
    host, port, username, password = mock_onvif_camera_cls.call_args.args[:4]
    assert (host, port, username, password) == (HOST, PORT, USERNAME, PASSWORD)


async def test_setup_entry_snapshot_probe_never_completes(hass: HomeAssistant) -> None:
    """Test a snapshot endpoint that never ends does not hold up setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
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

    async def _never_ends(profile_token: str, basic_auth: bool = False) -> bytes:
        await asyncio.Event().wait()
        return b""

    with (
        patch("homeassistant.components.onvif.device.ONVIFCamera") as mock_camera_cls,
        patch("homeassistant.components.onvif.SNAPSHOT_TIMEOUT", 0),
    ):
        setup_mock_onvif_camera(mock_camera_cls, with_full_setup=True)
        media_service = mock_camera_cls.create_media_service.return_value
        media_service.GetServiceCapabilities.return_value = SimpleNamespace(
            SnapshotUri=True
        )
        mock_camera_cls.get_snapshot.side_effect = _never_ends

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # nothing learned about the snapshot auth, so setup will probe again next time
    assert CONF_SNAPSHOT_AUTH not in entry.data
