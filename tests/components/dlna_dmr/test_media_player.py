"""Tests for the DLNA DMR media_player module."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock, create_autospec, patch

import aiohttp
import defusedxml.ElementTree as DET

from homeassistant.components import ssdp
from homeassistant.components.dlna_dmr import media_player
from homeassistant.components.dlna_dmr.const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN as DLNA_DOMAIN,
)
from homeassistant.components.dlna_dmr.data import get_domain_data
from homeassistant.components.dlna_dmr.media_player import DlnaDmrEntity
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from .conftest import (
    GOOD_DEVICE_BASE_URL,
    GOOD_DEVICE_LOCATION,
    GOOD_DEVICE_NAME,
    GOOD_DEVICE_TYPE,
    GOOD_DEVICE_UDN,
    GOOD_DEVICE_USN,
    SUBSCRIPTION_UUID_AVT,
    SUBSCRIPTION_UUID_RC,
    UNCONTACTABLE_DEVICE_LOCATION,
)

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


async def test_setup_entry_no_options(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    device_requests_mock: AiohttpClientMocker,
) -> None:
    """Test async_setup_entry creates a DlnaDmrEntity when no options are set."""
    mock_add_entities = create_autospec(AddEntitiesCallback)
    await media_player.async_setup_entry(hass, config_entry_mock, mock_add_entities)

    assert mock_add_entities.call_count == 1
    added_entities = mock_add_entities.call_args[0][0]
    assert len(added_entities) == 1
    entity = added_entities[0]
    assert isinstance(entity, media_player.DlnaDmrEntity)
    assert entity.poll_availability is False


async def test_setup_entry_with_options(
    hass: HomeAssistant, device_requests_mock: AiohttpClientMocker
) -> None:
    """Test setting options leads to a DlnaDmrEntity with custom event_handler."""
    config_entry = MockConfigEntry(
        unique_id=GOOD_DEVICE_USN,
        domain=DLNA_DOMAIN,
        data={
            CONF_URL: GOOD_DEVICE_LOCATION,
            CONF_DEVICE_ID: GOOD_DEVICE_UDN,
            CONF_TYPE: GOOD_DEVICE_TYPE,
        },
        title=GOOD_DEVICE_NAME,
        options={
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://192.88.99.10/events",
            CONF_POLL_AVAILABILITY: True,
        },
    )
    config_entry.add_to_hass(hass)
    mock_add_entities = create_autospec(AddEntitiesCallback)
    await media_player.async_setup_entry(hass, config_entry, mock_add_entities)

    assert mock_add_entities.call_count == 1
    added_entities = mock_add_entities.call_args[0][0]
    assert len(added_entities) == 1
    entity = added_entities[0]
    assert isinstance(entity, media_player.DlnaDmrEntity)
    assert entity.poll_availability is True
    assert entity._event_addr.port == 2222
    assert entity._event_addr.callback_url == "http://192.88.99.10/events"


UPNP_CTRL_RESPONSE_BLANK = """<?xml version="1.0" encoding="utf-8"?><s:Envelope
xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
    <u:{request_tag}Response xmlns:u="{namespace}">
    </u:{request_tag}Response>
    </s:Body>
</s:Envelope>"""


async def avt_ctrl_response(method, url, data):
    """Respond to AVT control request based on request data.

    AiohttpClientMockResponse can't filter based on headers, but we need to send
    different responses depending on the request.
    """
    del method, url
    # data should be a SOAP request. Determine request type based on child of
    # Body element
    request = DET.fromstring(data)
    namespace, _, req_type = request.find(".//{*}Body/*").tag.rpartition("}")
    namespace = namespace.lstrip("{")

    if req_type == "GetTransportInfo":
        return AiohttpClientMockResponse(
            method="POST",
            url=GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
            text=load_fixture("dlna_dmr/avt_ctrl_get_transport_info.xml"),
        )
    if req_type == "GetPositionInfo":
        return AiohttpClientMockResponse(
            method="POST",
            url=GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
            text=load_fixture("dlna_dmr/avt_ctrl_get_position_info.xml"),
        )

    # In all other cases, use a generic blank response
    response_text = UPNP_CTRL_RESPONSE_BLANK.format(
        request_tag=req_type, namespace=namespace
    )
    return AiohttpClientMockResponse(
        method="POST",
        url=GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
        text=response_text,
    )


async def rc_ctrl_response(method, url, data):
    """Respond to Rendering Control request based on request data.

    AiohttpClientMockResponse can't filter based on headers, but we need to send
    different responses depending on the request.
    """
    del method, url
    # data should be a SOAP request. Determine request type based on child of
    # Body element
    request = DET.fromstring(data)
    namespace, _, req_type = request.find(".//{*}Body/*").tag.rpartition("}")
    namespace = namespace.lstrip("{")

    response_text = UPNP_CTRL_RESPONSE_BLANK.format(
        request_tag=req_type, namespace=namespace
    )
    return AiohttpClientMockResponse(
        method="POST",
        url=GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
        text=response_text,
    )


async def make_dmr_entity(
    hass: HomeAssistant,
    data_override: Mapping[str, Any] = {},
    options_override: Mapping[str, Any] = {},
) -> DlnaDmrEntity:
    """Set up the platform, the config entry, and an entity we're going to test."""
    data: dict[str, Any] = {
        CONF_URL: GOOD_DEVICE_LOCATION,
        CONF_DEVICE_ID: GOOD_DEVICE_UDN,
        CONF_TYPE: GOOD_DEVICE_TYPE,
    }
    data.update(data_override)

    options: dict[str, Any] = {
        CONF_LISTEN_PORT: None,
        CONF_CALLBACK_URL_OVERRIDE: None,
        CONF_POLL_AVAILABILITY: False,
    }
    options.update(options_override)

    config_entry = MockConfigEntry(
        unique_id=GOOD_DEVICE_USN,
        domain=DLNA_DOMAIN,
        data=data,
        title=GOOD_DEVICE_NAME,
        options=options,
    )
    config_entry.add_to_hass(hass)
    await async_setup_component(hass, DLNA_DOMAIN, {})
    await hass.async_block_till_done()

    # Device should be fully constructed and added to hass now. Retrieve it.
    entity_comp = hass.data["entity_components"]["media_player"]
    assert entity_comp
    entity: DlnaDmrEntity = entity_comp.get_entity(
        f"media_player.{slugify(GOOD_DEVICE_NAME)}"
    )
    assert entity

    return entity


async def send_initial_event_notifications(entity: DlnaDmrEntity) -> None:
    """Send UPnP event notifications to update  state of entity._device.

    This is expected after an event subscription is first made.
    """
    assert entity._device is not None
    event_url = entity._device._event_handler.callback_url
    rc_event_xml = load_fixture("dlna_dmr/rc_event.xml")
    avt_event_xml = load_fixture("dlna_dmr/avt_event.xml")
    async with aiohttp.ClientSession() as event_client:
        await event_client.request(
            "NOTIFY",
            event_url,
            headers={
                "SID": SUBSCRIPTION_UUID_RC,
                "NT": "upnp:event",
                "NTS": "upnp:propchange",
            },
            data=rc_event_xml,
        )
        await event_client.request(
            "NOTIFY",
            event_url,
            headers={
                "SID": SUBSCRIPTION_UUID_AVT,
                "NT": "upnp:event",
                "NTS": "upnp:propchange",
            },
            data=avt_event_xml,
        )


async def test_device_available(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
    mock_ssdp_scanner: Mock,
) -> None:
    """Test a DlnaDmrEntity with a connected DmrDevice."""
    # The physical device should not have been contacted yet
    assert device_requests_mock.call_count == 0

    entity = await make_dmr_entity(hass, {CONF_URL: GOOD_DEVICE_LOCATION})

    assert entity._device is not None

    # Check device was contacted
    assert device_requests_mock.call_count > 0
    # Check UPnP services are subscribed
    assert set(entity._device._subscriptions.keys()) == {
        SUBSCRIPTION_UUID_RC,
        SUBSCRIPTION_UUID_AVT,
    }
    # Check SSDP notifications are registered
    mock_ssdp_scanner.async_register_callback.assert_called_once_with(
        entity._async_ssdp_notified, {"USN": GOOD_DEVICE_USN}
    )

    await send_initial_event_notifications(entity)

    # Check async_update will retrieve state from the device
    device_requests_mock.clear_requests()
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
        side_effect=avt_ctrl_response,
    )

    await entity.async_update()
    assert 1 <= device_requests_mock.call_count <= 2

    # Check hass device information is filled in
    assert entity.device_info == {
        "connections": {("upnp", GOOD_DEVICE_UDN)},
        "manufacturer": "Dummy corp",
        "model": "Dummy model name",
        "name": "Test Receiver Device",
    }

    # Check all interface properties provide non-None results
    assert entity.available is True
    assert entity.supported_features == 0x523F  # Specific to the device fixture
    assert entity.volume_level == 0.24
    assert entity.is_volume_muted is False
    assert entity.media_title == "Song of Fakeness"
    assert entity.media_image_url == "http://192.88.99.20:8200/AlbumArt/2624-17620.jpg"
    assert entity.state == "playing"
    assert entity.media_duration == 226
    assert entity.media_position == 99

    # Check all interface methods send a request to the device
    device_requests_mock.clear_requests()
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
        side_effect=avt_ctrl_response,
    )
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/RenderingControl/ctrl", side_effect=rc_ctrl_response
    )
    await entity.async_set_volume_level(0.80)
    assert device_requests_mock.call_count == 1
    await entity.async_mute_volume(True)
    assert device_requests_mock.call_count == 2
    await entity.async_media_pause()
    assert device_requests_mock.call_count == 3
    await entity.async_media_play()
    assert device_requests_mock.call_count == 4
    await entity.async_media_stop()
    assert device_requests_mock.call_count == 5
    await entity.async_media_previous_track()
    assert device_requests_mock.call_count == 6
    await entity.async_media_next_track()
    assert device_requests_mock.call_count == 7
    await entity.async_media_seek(33)
    assert device_requests_mock.call_count == 8
    # play_media does 2 calls: Stop then SetTransportUri (not media_play because
    # fake device is already "playing")
    await entity.async_play_media(
        "music", "http://192.88.99.20:8200/MediaItems/17621.mp3"
    )
    assert device_requests_mock.call_count == 10

    # Setup requests mock to verify UPnP services are unsubscribed
    device_requests_mock.clear_requests()
    device_requests_mock.request(
        "UNSUBSCRIBE", GOOD_DEVICE_BASE_URL + "/RenderingControl/evt"
    )
    device_requests_mock.request(
        "UNSUBSCRIBE", GOOD_DEVICE_BASE_URL + "/AVTransport/evt"
    )

    # Removing entity cancels callback and disconnects from device
    await entity.async_remove()
    # Check device is gone
    assert entity._device is None
    # Verify UPnP services are unsubscribed
    assert device_requests_mock.call_count == 2
    # Check SSDP notifications are cleared
    mock_ssdp_scanner.async_register_callback.return_value.assert_called_once()


async def test_device_unavailable(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
    mock_ssdp_scanner: Mock,
) -> None:
    """Test a DlnaDmrEntity with out a connected DmrDevice."""
    # The physical device should not have been contacted yet
    assert device_requests_mock.call_count == 0

    entity = await make_dmr_entity(hass, {CONF_URL: UNCONTACTABLE_DEVICE_LOCATION})

    assert entity._device is None

    # Physical device should have been contacted only once, getting a timeout
    assert device_requests_mock.call_count == 1

    # Check SSDP notifications are registered
    mock_ssdp_scanner.async_register_callback.assert_called_once_with(
        entity._async_ssdp_notified, {"USN": GOOD_DEVICE_USN}
    )

    # Check async_update will do nothing
    device_requests_mock.clear_requests()
    await entity.async_update()
    assert device_requests_mock.call_count == 0

    # Check hass device information is missing
    assert entity.device_info is None
    assert entity.supported_features == 0

    # Device is not available, and hass should know it
    assert entity.available is False
    assert entity.state == "off"

    # Check all interface properties return None
    assert entity.volume_level is None
    assert entity.is_volume_muted is None
    assert entity.media_title is None
    assert entity.media_image_url is None
    assert entity.media_duration is None
    assert entity.media_position is None

    # Check all interface methods do nothing
    device_requests_mock.clear_requests()
    await entity.async_set_volume_level(0.80)
    await entity.async_mute_volume(True)
    await entity.async_media_pause()
    await entity.async_media_play()
    await entity.async_media_stop()
    await entity.async_media_previous_track()
    await entity.async_media_next_track()
    await entity.async_media_seek(33)
    await entity.async_play_media(
        "music", "http://192.88.99.20:8200/MediaItems/17621.mp3"
    )
    assert device_requests_mock.call_count == 0

    # Removing entity cancels SSDP callback but does not contact device
    await entity.async_remove()
    mock_ssdp_scanner.async_register_callback.return_value.assert_called_once()
    assert device_requests_mock.call_count == 0


async def test_become_available(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
    mock_ssdp_scanner: Mock,
) -> None:
    """Test a device becoming available after the entity is constructed."""
    entity: DlnaDmrEntity = await make_dmr_entity(
        hass, {CONF_URL: UNCONTACTABLE_DEVICE_LOCATION}
    )

    # Send an SSDP notification with the new device URL
    assert device_requests_mock.call_count == 1
    entity._async_ssdp_notified(
        {
            ssdp.ATTR_SSDP_USN: GOOD_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: GOOD_DEVICE_LOCATION,
        }
    )
    await hass.async_block_till_done()

    # Device should be contacted, and entity should be updated
    assert device_requests_mock.call_count > 1
    assert entity.location == GOOD_DEVICE_LOCATION
    assert entity._device is not None
    assert entity.available is True
    assert entity.supported_features == 0x523F

    # Perform UPnP event notification dance
    assert set(entity._device._subscriptions.keys()) == {
        SUBSCRIPTION_UUID_RC,
        SUBSCRIPTION_UUID_AVT,
    }
    await send_initial_event_notifications(entity)

    # Quick check that interface now works
    assert entity.volume_level == 0.24
    device_requests_mock.clear_requests()
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/RenderingControl/ctrl", side_effect=rc_ctrl_response
    )
    await entity.async_set_volume_level(0.80)
    assert device_requests_mock.call_count == 1

    # Setup requests mock to verify UPnP services are unsubscribed
    device_requests_mock.clear_requests()
    device_requests_mock.request(
        "UNSUBSCRIBE", GOOD_DEVICE_BASE_URL + "/RenderingControl/evt"
    )
    device_requests_mock.request(
        "UNSUBSCRIBE", GOOD_DEVICE_BASE_URL + "/AVTransport/evt"
    )

    # Removing entity cancels callback and disconnects from device
    await entity.async_remove()
    # Check device is gone
    assert entity._device is None
    # Verify UPnP services are unsubscribed
    assert device_requests_mock.call_count == 2
    # Check SSDP notifications are cleared
    mock_ssdp_scanner.async_register_callback.return_value.assert_called_once()


async def test_multiple_ssdp_alive(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
    mock_ssdp_scanner: Mock,
) -> None:
    """Test multiple SSDP alive notifications is ok, only connects to device once."""
    entity: DlnaDmrEntity = await make_dmr_entity(
        hass, {CONF_URL: UNCONTACTABLE_DEVICE_LOCATION}
    )
    assert device_requests_mock.call_count == 1

    domain_data = get_domain_data(hass)
    create_device_orig = domain_data.upnp_factory.async_create_device

    async def create_device_delayed(location):
        """Delay before continuing with async_create_device.

        This gives a chance for parallel calls to `_device_connect` to occur.
        """
        await asyncio.sleep(0.1)
        return await create_device_orig(location)

    with patch.object(
        domain_data.upnp_factory,
        "async_create_device",
        side_effect=create_device_delayed,
    ) as create_device_mock:

        # Send two SSDP notifications with the new device URL
        entity._async_ssdp_notified(
            {
                ssdp.ATTR_SSDP_USN: GOOD_DEVICE_USN,
                ssdp.ATTR_SSDP_LOCATION: GOOD_DEVICE_LOCATION,
            }
        )
        entity._async_ssdp_notified(
            {
                ssdp.ATTR_SSDP_USN: GOOD_DEVICE_USN,
                ssdp.ATTR_SSDP_LOCATION: GOOD_DEVICE_LOCATION,
            }
        )
        await hass.async_block_till_done()

    # Check device is contacted exactly once
    assert create_device_mock.call_count == 1

    # Device should be contacted, and entity should be updated
    assert device_requests_mock.call_count > 1
    assert entity.location == GOOD_DEVICE_LOCATION
    assert entity._device is not None
    assert entity.available is True
    assert entity.supported_features == 0x523F


async def test_become_unavailable(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
    mock_ssdp_scanner: Mock,
) -> None:
    """Test a device becoming unavailable."""
    # Setup device as for test_device_available
    entity = await make_dmr_entity(hass, {CONF_URL: GOOD_DEVICE_LOCATION})

    assert entity._device is not None
    await send_initial_event_notifications(entity)

    # Check async_update currently works
    device_requests_mock.clear_requests()
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
        side_effect=avt_ctrl_response,
    )

    await entity.async_update()
    assert 1 <= device_requests_mock.call_count <= 2

    # Now break the network connection and try to contact the device
    device_requests_mock.clear_requests()
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl", exc=asyncio.TimeoutError
    )
    device_requests_mock.request(
        "UNSUBSCRIBE",
        GOOD_DEVICE_BASE_URL + "/RenderingControl/evt",
        exc=asyncio.TimeoutError,
    )
    device_requests_mock.request(
        "UNSUBSCRIBE",
        GOOD_DEVICE_BASE_URL + "/AVTransport/evt",
        exc=asyncio.TimeoutError,
    )
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/RenderingControl/ctrl", exc=asyncio.TimeoutError
    )
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
        exc=asyncio.TimeoutError,
    )

    # Interface method calls should flag that the device is unavailable, but not
    # disconnect it immediately
    assert entity.check_available is False
    await entity.async_set_volume_level(0.80)
    assert entity._device is not None
    assert entity.check_available is True

    # An update will cause the device to be disconnected
    await entity.async_update()
    assert entity._device is None
    assert entity.check_available is False


async def test_poll_availability(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
) -> None:
    """Test device becomes available and noticed via poll_availability."""
    entity: DlnaDmrEntity = await make_dmr_entity(
        hass,
        {CONF_URL: UNCONTACTABLE_DEVICE_LOCATION},
        {CONF_POLL_AVAILABILITY: True},
    )

    assert entity._device is None
    assert device_requests_mock.call_count == 2

    # Check that an update will poll the device for availability
    await entity.async_update()
    assert entity._device is None
    assert device_requests_mock.call_count == 3

    # Change the device location to use the normal device_requests_mock
    entity.location = GOOD_DEVICE_LOCATION

    # Check that an update will notice the device and connect to it
    device_requests_mock.post(
        GOOD_DEVICE_BASE_URL + "/AVTransport/ctrl",
        side_effect=avt_ctrl_response,
    )
    await entity.async_update()
    assert entity._device is not None


async def test_resubscribe_failure(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
) -> None:
    """Test failure to resubscribe to events notifications causes an update ping."""
    entity = await make_dmr_entity(hass, {CONF_URL: GOOD_DEVICE_LOCATION})

    assert entity._device is not None
    assert entity.check_available is False
    entity._on_event(
        entity._device.device.services["urn:schemas-upnp-org:service:AVTransport:1"], []
    )
    assert entity.check_available is True


async def test_config_update(
    hass: HomeAssistant,
    device_requests_mock: AiohttpClientMocker,
    mock_ssdp_scanner: Mock,
) -> None:
    """Test DlnaDmrEntity gets updated when associated ConfigEntry does."""
    # Create a config entry and device fixture
    config_entry = MockConfigEntry(
        unique_id=GOOD_DEVICE_USN,
        domain=DLNA_DOMAIN,
        data={
            CONF_URL: GOOD_DEVICE_LOCATION,
            CONF_DEVICE_ID: GOOD_DEVICE_UDN,
            CONF_TYPE: GOOD_DEVICE_TYPE,
        },
        title=GOOD_DEVICE_NAME,
        options={},
    )
    config_entry.add_to_hass(hass)
    await async_setup_component(hass, DLNA_DOMAIN, {})
    await hass.async_block_till_done()

    entity_comp = hass.data["entity_components"]["media_player"]
    assert entity_comp
    entity: DlnaDmrEntity = entity_comp.get_entity(
        f"media_player.{slugify(GOOD_DEVICE_NAME)}"
    )
    assert entity._device is not None
    assert device_requests_mock.call_count == 6

    # Update the config entry one option at a time and check the device also
    # updates. Order is important due to port binding of event listener.
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_CALLBACK_URL_OVERRIDE: "http://example.com",
        },
    )
    await hass.async_block_till_done()
    assert entity._device is not None
    # Device will be reconnected
    assert device_requests_mock.call_count == 14
    assert entity._event_addr.callback_url == "http://example.com"

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_CALLBACK_URL_OVERRIDE: "http://example.com",
            CONF_LISTEN_PORT: 1234,
        },
    )
    await hass.async_block_till_done()
    assert entity._device is not None
    # Device will be reconnected
    assert device_requests_mock.call_count == 22
    assert entity._event_addr.port == 1234

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_CALLBACK_URL_OVERRIDE: "http://example.com",
            CONF_LISTEN_PORT: 1234,
            CONF_POLL_AVAILABILITY: True,
        },
    )
    await hass.async_block_till_done()
    assert entity._device is not None
    # Device will *not* be reconnected
    assert device_requests_mock.call_count == 22
    assert entity.poll_availability is True
