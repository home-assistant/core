"""Configuration for AV Receiver tests."""
from unittest.mock import AsyncMock, Mock, patch as patch

from pyavreceiver import const
from pyavreceiver.dispatch import Dispatcher
from pyavreceiver.receiver import AVReceiver
from pyavreceiver.zone import MainZone, Zone
import pytest

from homeassistant.components import ssdp
from homeassistant.components.avreceiver import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock AVReceiver config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        title="AV Receiver (127.0.0.1)",
        unique_id=f"{DOMAIN}-127.0.0.1",
    )


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {CONF_HOST: "127.0.0.1"}}


@pytest.fixture(name="dispatcher")
def dispatcher_fixture() -> Dispatcher:
    """Create a dispatcher for testing."""
    return Dispatcher()


@pytest.fixture(name="controller")
def controller_fixture(dispatcher, zones):
    """Create a mock AVR controller fixture."""
    # pylint: disable=protected-access
    mock_avr = Mock(AVReceiver)
    mock_avr.friendly_name = "Test Device"
    mock_avr.dispatcher = dispatcher
    mock_avr.connection_state = const.STATE_CONNECTED
    mock_avr.serial_number = "serial"
    mock_avr.main = zones["main"]
    mock_avr.host = ""
    mock_avr.manufacturer = ""
    mock_avr.model = ""
    zones["main"]._avr = mock_avr
    mock_avr.zone2 = zones["zone2"]
    zones["zone2"]._avr = mock_avr
    mock_avr.state = {}
    mock = AsyncMock(return_value=mock_avr)
    with patch("homeassistant.components.avreceiver.factory", new=mock), patch(
        "homeassistant.components.avreceiver.config_flow.factory", new=mock
    ):
        yield mock_avr


@pytest.fixture(name="zones")
def zone_fixture():
    """Create a mock AV Receiver Zone."""
    zone = Mock(Zone)
    zone.name = "Test Zone"
    zone.friendly_name = "Test Zone"
    zone.model = "Test Model"
    zone.version = "1.0.0"
    zone.is_muted = False
    zone.available = True
    zone.state = "on"
    zone.source_list = ["source1, source2"]
    zone.volume = 25
    zone.max_volume = 0
    zone.min_volume = -80
    zone.state = {}
    zone.ip_address = "127.0.0.1"
    zone.set = Mock(return_value=True)

    main_zone = Mock(MainZone)
    main_zone.name = "Test Main Zone"
    main_zone.friendly_name = "Test Main Zone"
    main_zone.model = "Test Model"
    main_zone.version = "1.0.0"
    main_zone.is_muted = False
    main_zone.available = True
    main_zone.state = "on"
    main_zone.volume = 25
    main_zone.source_list = ["source1, source2"]
    main_zone.sound_mode_list = ["Direct", "Auto"]
    main_zone.soundmode = "Dolby"
    main_zone.max_volume = 0
    main_zone.min_volume = -80
    main_zone.state = {}
    main_zone.ip_address = "127.0.0.1"
    main_zone.set = AsyncMock(return_value=True)
    main_zone.set_mute = AsyncMock(return_value=True)
    main_zone.set_power = AsyncMock(return_value=True)
    main_zone.set_volume = AsyncMock(return_value=True)
    main_zone.set_source = AsyncMock(return_value=True)
    main_zone.set_soundmode = AsyncMock(return_value=True)
    main_zone.update_all = AsyncMock(return_value=None)
    return {"main": main_zone, "zone2": zone}


@pytest.fixture(name="discovery_data")
def discovery_data_fixture() -> dict:
    """Return mock discovery data for testing."""
    return {
        ssdp.ATTR_SSDP_LOCATION: "http://127.0.0.1:60006/upnp/desc/aios_device/aios_device.xml",
        ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-denon-com:device:AiosDevice:1",
        ssdp.ATTR_UPNP_FRIENDLY_NAME: "Office",
        ssdp.ATTR_UPNP_MANUFACTURER: "Denon",
        ssdp.ATTR_UPNP_MODEL_NAME: "AVR-X1500H",
        ssdp.ATTR_UPNP_MODEL_NUMBER: "DWSA-10 4.0",
        ssdp.ATTR_UPNP_SERIAL: "serial",
        ssdp.ATTR_UPNP_UDN: "uuid:e61de70c-2250-1c22-0080-0005cdf512be",
    }
