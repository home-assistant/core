"""Test how the DmsDeviceSource handles available and unavailable devices."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
import logging
from unittest.mock import ANY, DEFAULT, Mock

from async_upnp_client.exceptions import UpnpConnectionError, UpnpError
from didl_lite import didl_lite
import pytest

from homeassistant.components import media_source, ssdp
from homeassistant.components.dlna_dms.const import DOMAIN
from homeassistant.components.dlna_dms.dms import DmsDeviceSource, get_domain_data
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_DEVICE_LOCATION,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_TYPE,
    MOCK_DEVICE_UDN,
    MOCK_DEVICE_USN,
    MOCK_SOURCE_ID,
    NEW_DEVICE_LOCATION,
)

from tests.common import MockConfigEntry

# Auto-use a few fixtures from conftest
pytestmark = [
    # Block network access
    pytest.mark.usefixtures("aiohttp_session_requester_mock"),
    pytest.mark.usefixtures("dms_device_mock"),
    # Setup the media_source platform
    pytest.mark.usefixtures("setup_media_source"),
]


async def setup_mock_component(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> DmsDeviceSource:
    """Set up a mock DmsDeviceSource with the given configuration."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    domain_data = get_domain_data(hass)
    return next(iter(domain_data.devices.values()))


@pytest.fixture
async def disconnected_source_mock(
    hass: HomeAssistant,
    upnp_factory_mock: Mock,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
) -> AsyncIterable[DmsDeviceSource]:
    """Fixture to set up a mock DmsDeviceSource in a disconnected state.

    Yields the entity. Cleans up the entity after the test is complete.
    """
    # Cause the connection attempt to fail
    upnp_factory_mock.async_create_device.side_effect = UpnpConnectionError

    config_entry_mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    domain_data = get_domain_data(hass)
    device_source = domain_data.devices[MOCK_DEVICE_USN]

    # Check the device source has registered all needed listeners
    assert len(config_entry_mock.update_listeners) == 1
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 0

    # Run the test
    yield device_source

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Check device source has cleaned up its resources
    assert not config_entry_mock.update_listeners
    assert (
        ssdp_scanner_mock.async_register_callback.await_count
        == ssdp_scanner_mock.async_register_callback.return_value.call_count
    )


async def test_unavailable_device(
    hass: HomeAssistant,
    upnp_factory_mock: Mock,
    ssdp_scanner_mock: Mock,
    disconnected_source_mock: DmsDeviceSource,
) -> None:
    """Test a DlnaDmsEntity with out a connected DmsDevice."""
    # Check attempt was made to create a device from the supplied URL
    upnp_factory_mock.async_create_device.assert_awaited_once_with(MOCK_DEVICE_LOCATION)
    # Check SSDP notifications are registered
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"USN": MOCK_DEVICE_USN}
    )
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"_udn": MOCK_DEVICE_UDN, "NTS": "ssdp:byebye"}
    )
    # Quick check of the state to verify the entity has no connected DmsDevice
    assert not disconnected_source_mock.available
    # Check the name matches that supplied
    assert disconnected_source_mock.name == MOCK_DEVICE_NAME

    # Check attempts to browse and resolve media give errors
    with pytest.raises(BrowseError, match="DMS is not connected"):
        await media_source.async_browse_media(
            hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}//browse_path"
        )
    with pytest.raises(BrowseError, match="DMS is not connected"):
        await media_source.async_browse_media(
            hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/:browse_object"
        )
    with pytest.raises(BrowseError, match="DMS is not connected"):
        await media_source.async_browse_media(
            hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/?browse_search"
        )
    with pytest.raises(Unresolvable, match="DMS is not connected"):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}//resolve_path"
        )
    with pytest.raises(Unresolvable, match="DMS is not connected"):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/:resolve_object"
        )
    with pytest.raises(Unresolvable):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/?resolve_search"
        )


async def test_become_available(
    hass: HomeAssistant,
    upnp_factory_mock: Mock,
    ssdp_scanner_mock: Mock,
    disconnected_source_mock: DmsDeviceSource,
) -> None:
    """Test a device becoming available after the entity is constructed."""
    # Mock device is now available.
    upnp_factory_mock.async_create_device.side_effect = None
    upnp_factory_mock.async_create_device.reset_mock()

    # Send an SSDP notification from the now alive device
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Check device was created from the supplied URL
    upnp_factory_mock.async_create_device.assert_awaited_once_with(NEW_DEVICE_LOCATION)
    # Quick check of the state to verify the entity has a connected DmsDevice
    assert disconnected_source_mock.available


async def test_alive_but_gone(
    hass: HomeAssistant,
    upnp_factory_mock: Mock,
    ssdp_scanner_mock: Mock,
    disconnected_source_mock: DmsDeviceSource,
) -> None:
    """Test a device sending an SSDP alive announcement, but not being connectable."""
    upnp_factory_mock.async_create_device.side_effect = UpnpError

    # Send an SSDP notification from the still missing device
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # There should be a connection attempt to the device
    upnp_factory_mock.async_create_device.assert_awaited()

    # Device should still be unavailable
    assert not disconnected_source_mock.available

    # Send the same SSDP notification, expecting no extra connection attempts
    upnp_factory_mock.async_create_device.reset_mock()
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()
    upnp_factory_mock.async_create_device.assert_not_called()
    upnp_factory_mock.async_create_device.assert_not_awaited()
    assert not disconnected_source_mock.available

    # Send an SSDP notification with a new BOOTID, indicating the device has rebooted
    upnp_factory_mock.async_create_device.reset_mock()
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Rebooted device (seen via BOOTID) should mean a new connection attempt
    upnp_factory_mock.async_create_device.assert_awaited()
    assert not disconnected_source_mock.available

    # Send byebye message to indicate device is going away. Next alive message
    # should result in a reconnect attempt even with same BOOTID.
    upnp_factory_mock.async_create_device.reset_mock()
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.BYEBYE,
    )
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Rebooted device (seen via byebye/alive) should mean a new connection attempt
    upnp_factory_mock.async_create_device.assert_awaited()
    assert not disconnected_source_mock.available


async def test_multiple_ssdp_alive(
    hass: HomeAssistant,
    upnp_factory_mock: Mock,
    ssdp_scanner_mock: Mock,
    disconnected_source_mock: DmsDeviceSource,
) -> None:
    """Test multiple SSDP alive notifications is ok, only connects to device once."""
    upnp_factory_mock.async_create_device.reset_mock()

    # Contacting the device takes long enough that 2 simultaneous attempts could be made
    async def create_device_delayed(_location):
        """Delay before continuing with async_create_device.

        This gives a chance for parallel calls to `device_connect` to occur.
        """
        await asyncio.sleep(0.1)
        return DEFAULT

    upnp_factory_mock.async_create_device.side_effect = create_device_delayed

    # Send two SSDP notifications with the new device URL
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Check device is contacted exactly once
    upnp_factory_mock.async_create_device.assert_awaited_once_with(NEW_DEVICE_LOCATION)

    # Device should be available
    assert disconnected_source_mock.available


async def test_ssdp_byebye(
    ssdp_scanner_mock: Mock,
    device_source_mock: DmsDeviceSource,
) -> None:
    """Test device is disconnected when byebye is received."""
    # First byebye will cause a disconnect
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={"NTS": "ssdp:byebye"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.BYEBYE,
    )

    # Device should be gone
    assert not device_source_mock.available

    # Second byebye will do nothing
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={"NTS": "ssdp:byebye"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.BYEBYE,
    )


async def test_ssdp_update_seen_bootid(
    hass: HomeAssistant,
    ssdp_scanner_mock: Mock,
    upnp_factory_mock: Mock,
    disconnected_source_mock: DmsDeviceSource,
) -> None:
    """Test device does not reconnect when it gets ssdp:update with next bootid."""
    # Start with a disconnected device
    entity = disconnected_source_mock
    assert not entity.available

    # "Reconnect" the device
    upnp_factory_mock.async_create_device.reset_mock()
    upnp_factory_mock.async_create_device.side_effect = None

    # Send SSDP alive with boot ID
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Device should be connected
    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send SSDP update with next boot ID
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "1",
                ssdp.ATTR_SSDP_NEXTBOOTID: "2",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Device was not reconnected, even with a new boot ID
    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send SSDP update with same next boot ID, again
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "1",
                ssdp.ATTR_SSDP_NEXTBOOTID: "2",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Nothing should change
    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send SSDP update with bad next boot ID
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "2",
                ssdp.ATTR_SSDP_NEXTBOOTID: "7c848375-a106-4bd1-ac3c-8e50427c8e4f",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Nothing should change
    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send a new SSDP alive with the new boot ID, device should not reconnect
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1


async def test_ssdp_update_missed_bootid(
    hass: HomeAssistant,
    ssdp_scanner_mock: Mock,
    upnp_factory_mock: Mock,
    disconnected_source_mock: DmsDeviceSource,
) -> None:
    """Test device disconnects when it gets ssdp:update bootid it wasn't expecting."""
    # Start with a disconnected device
    entity = disconnected_source_mock
    assert not entity.available

    # "Reconnect" the device
    upnp_factory_mock.async_create_device.reset_mock()
    upnp_factory_mock.async_create_device.side_effect = None

    # Send SSDP alive with boot ID
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Device should be connected
    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send SSDP update with skipped boot ID (not previously seen)
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "2",
                ssdp.ATTR_SSDP_NEXTBOOTID: "3",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Device should not *re*-connect yet
    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send a new SSDP alive with the new boot ID, device should reconnect
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "3"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 2


async def test_ssdp_bootid(
    hass: HomeAssistant,
    upnp_factory_mock: Mock,
    ssdp_scanner_mock: Mock,
    disconnected_source_mock: DmsDeviceSource,
) -> None:
    """Test an alive with a new BOOTID.UPNP.ORG header causes a reconnect."""
    # Start with a disconnected device
    entity = disconnected_source_mock
    assert not entity.available

    # "Reconnect" the device
    upnp_factory_mock.async_create_device.side_effect = None
    upnp_factory_mock.async_create_device.reset_mock()

    # Send SSDP alive with boot ID
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send SSDP alive with same boot ID, nothing should happen
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    assert entity.available
    assert upnp_factory_mock.async_create_device.await_count == 1

    # Send a new SSDP alive with an incremented boot ID, device should be dis/reconnected
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    await assert_source_available(hass)
    assert upnp_factory_mock.async_create_device.await_count == 2


async def test_repeated_connect(
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
    upnp_factory_mock: Mock,
    connected_source_mock: None,
) -> None:
    """Test trying to connect an already connected device is safely ignored."""
    upnp_factory_mock.async_create_device.reset_mock()

    # Calling internal function directly to skip trying to time 2 SSDP messages carefully
    with caplog.at_level(logging.DEBUG):
        await disconnected_source_mock.device_connect()
    assert "Not connecting because location is not known" == caplog.records[-1].message
    assert not upnp_factory_mock.async_create_device.await_count


async def test_become_unavailable(
    hass: HomeAssistant,
    connected_source_mock: None,
    dms_device_mock: Mock,
) -> None:
    """Test a device becoming unavailable."""
    # Mock a good resolve result
    dms_device_mock.async_browse_metadata.return_value = didl_lite.Item(
        id="object_id",
        restricted=False,
        title="Object",
        res=[didl_lite.Resource(uri="foo", protocol_info="http-get:*:audio/mpeg:")],
    )

    # Check async_resolve_object currently works
    assert await media_source.async_resolve_media(
        hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/:object_id"
    )

    # Now break the network connection
    dms_device_mock.async_browse_metadata.side_effect = UpnpConnectionError

    # The device should be considered available until next contacted
    assert device_source_mock.available

    # async_resolve_object should fail
    with pytest.raises(Unresolvable):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/:object_id"
        )

    # The device should now be unavailable
    assert not device_source_mock.available
