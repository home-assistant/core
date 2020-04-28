"""Test UPnP/IGD setup process."""

from ipaddress import IPv4Address

from asynctest import patch

from homeassistant.components import upnp
from homeassistant.components.upnp.device import Device
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


class MockDevice(Device):
    """Mock device for Device."""

    def __init__(self, udn):
        """Initialize mock device."""
        igd_device = object()
        super().__init__(igd_device)
        self._udn = udn
        self.added_port_mappings = []
        self.removed_port_mappings = []

    @classmethod
    async def async_create_device(cls, hass, ssdp_description):
        """Return self."""
        return cls("UDN")

    @property
    def udn(self) -> str:
        """Get the UDN."""
        return self._udn

    @property
    def manufacturer(self) -> str:
        """Get manufacturer."""
        return "mock-manufacturer"

    @property
    def name(self) -> str:
        """Get name."""
        return "mock-name"

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return "mock-model-name"

    @property
    def device_type(self) -> str:
        """Get the device type."""
        return "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

    async def _async_add_port_mapping(
        self, external_port: int, local_ip: str, internal_port: int
    ) -> None:
        """Add a port mapping."""
        entry = [external_port, local_ip, internal_port]
        self.added_port_mappings.append(entry)

    async def _async_delete_port_mapping(self, external_port: int) -> None:
        """Remove a port mapping."""
        entry = external_port
        self.removed_port_mappings.append(entry)


async def test_async_setup_entry_default(hass):
    """Test async_setup_entry."""
    udn = "uuid:device_1"
    entry = MockConfigEntry(domain=upnp.DOMAIN)

    config = {
        # no upnp
    }
    with patch.object(Device, "async_create_device") as create_device, patch.object(
        Device, "async_discover", return_value=mock_coro([])
    ) as async_discover:
        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()

        # mock homeassistant.components.upnp.device.Device
        mock_device = MockDevice(udn)
        discovery_infos = [
            {"udn": udn, "ssdp_description": "http://192.168.1.1/desc.xml"}
        ]

        create_device.return_value = mock_coro(return_value=mock_device)
        async_discover.return_value = mock_coro(return_value=discovery_infos)

        assert await upnp.async_setup_entry(hass, entry) is True

        # ensure device is stored/used
        assert hass.data[upnp.DOMAIN]["devices"][udn] == mock_device

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    # ensure no port-mappings created or removed
    assert not mock_device.added_port_mappings
    assert not mock_device.removed_port_mappings


async def test_async_setup_entry_port_mapping(hass):
    """Test async_setup_entry."""
    # pylint: disable=invalid-name
    udn = "uuid:device_1"
    entry = MockConfigEntry(domain=upnp.DOMAIN)

    config = {
        "http": {},
        "upnp": {
            "local_ip": "192.168.1.10",
            "port_mapping": True,
            "ports": {"hass": "hass"},
        },
    }
    with patch.object(Device, "async_create_device") as create_device, patch.object(
        Device, "async_discover", return_value=mock_coro([])
    ) as async_discover:
        await async_setup_component(hass, "http", config)
        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()

        mock_device = MockDevice(udn)
        discovery_infos = [
            {"udn": udn, "ssdp_description": "http://192.168.1.1/desc.xml"}
        ]

        create_device.return_value = mock_coro(return_value=mock_device)
        async_discover.return_value = mock_coro(return_value=discovery_infos)

        assert await upnp.async_setup_entry(hass, entry) is True

        # ensure device is stored/used
        assert hass.data[upnp.DOMAIN]["devices"][udn] == mock_device

        # ensure add-port-mapping-methods called
        assert mock_device.added_port_mappings == [
            [8123, IPv4Address("192.168.1.10"), 8123]
        ]

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    # ensure delete-port-mapping-methods called
    assert mock_device.removed_port_mappings == [8123]
