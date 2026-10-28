"""Tests for the DLNA DMR diagnostics."""

from unittest.mock import Mock

from async_upnp_client.exceptions import UpnpConnectionError
from async_upnp_client.profiles.dlna import PlayMode, TransportState
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.dlna_dmr.const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN,
)
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import EVENT_CALLBACK_URL, MOCK_DEVICE_UDN


@pytest.fixture
def connected_device(dmr_device_mock: Mock) -> Mock:
    """Populate the DMR device mock with realistic values."""
    profile_device = dmr_device_mock.profile_device
    profile_device.manufacturer = "device_manufacturer"
    profile_device.model_name = "device_model_name"
    profile_device.model_number = "1.0"
    profile_device.model_description = "Test renderer"
    for service in profile_device.all_services:
        service.actions = dict.fromkeys(
            {
                "urn:schemas-upnp-org:service:AVTransport:1": ["Play", "Pause", "Stop"],
                "urn:schemas-upnp-org:service:ConnectionManager:1": ["GetProtocolInfo"],
                "urn:schemas-upnp-org:service:RenderingControl:1": [
                    "GetVolume",
                    "SetVolume",
                ],
            }[service.service_type]
        )

    dmr_device_mock.sink_protocol_info = [
        "http-get:*:audio/mpeg:*",
        "http-get:*:video/mp4:*",
    ]
    dmr_device_mock.transport_state = TransportState.STOPPED
    dmr_device_mock.valid_play_modes = {PlayMode.NORMAL, PlayMode.REPEAT_ALL}
    dmr_device_mock.has_volume_level = True
    dmr_device_mock.has_volume_mute = False
    dmr_device_mock.has_presets = True
    dmr_device_mock.has_play_media = True
    dmr_device_mock.has_next_transport_uri = False
    dmr_device_mock.can_play = True
    dmr_device_mock.can_pause = True
    dmr_device_mock.can_stop = True
    dmr_device_mock.can_previous = False
    dmr_device_mock.can_next = False
    dmr_device_mock.can_seek_rel_time = False
    return dmr_device_mock


@pytest.mark.usefixtures("domain_data_mock", "connected_device")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_mock: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a connected device."""
    config_entry_mock.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: EVENT_CALLBACK_URL,
            CONF_POLL_AVAILABILITY: True,
        },
    )
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry_mock)
        == snapshot
    )


@pytest.mark.usefixtures("dmr_device_mock")
async def test_diagnostics_disconnected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when the device is not connected."""
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    config_entry_mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry_mock)
        == snapshot
    )


@pytest.mark.usefixtures("domain_data_mock", "connected_device")
async def test_diagnostics_entity_disabled(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    config_entry_mock: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when the media player entity is disabled."""
    config_entry_mock.add_to_hass(hass)
    entity_registry.async_get_or_create(
        MEDIA_PLAYER_DOMAIN,
        DOMAIN,
        MOCK_DEVICE_UDN,
        config_entry=config_entry_mock,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry_mock)
        == snapshot
    )
