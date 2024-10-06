"""Tests for the swidget integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from swidget import SwidgetDevice, SwidgetDimmer, SwidgetDiscoveredDevice
from swidget.exceptions import SwidgetException

from homeassistant.components.swidget import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MODULE = "homeassistant.components.swidget"
MODULE_CONFIG_FLOW = "homeassistant.components.swidget.config_flow"
IP_ADDRESS = "127.0.0.1"
IP_ADDRESS2 = "127.0.0.2"
FRIENDLY_NAME = "SWIDGET KITCHEN DIMMER"
MODEL = "HK_PICO_1"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"


def _mocked_dimmer(
    mac=MAC_ADDRESS,
) -> SwidgetDimmer:
    dimmer = MagicMock(auto_spec=SwidgetDimmer(), name="Mocked dimmer")
    dimmer.token_name = "x-secret-key"
    dimmer.ip_address = IP_ADDRESS
    dimmer.use_https = True
    dimmer.uri_scheme = "https"
    dimmer.secret_key = "secret"
    dimmer.use_websockets = False
    dimmer.device_type = SwidgetDimmer
    dimmer.insert_type = "USB"
    dimmer._friendly_name = "Unknown Swidget Device"
    dimmer.mac_address = mac
    dimmer.model = MODEL
    dimmer.version = "1.2.3"
    dimmer.update = AsyncMock()
    dimmer.mac_address = mac
    dimmer.turn_off = AsyncMock()
    dimmer.turn_on = AsyncMock()
    dimmer.set_brightness = AsyncMock()
    dimmer.turn_on_usb_insert = AsyncMock()
    dimmer.turn_off_usb_insert = AsyncMock()
    return dimmer


def _patch_discovery(device=None, no_device=False):
    async def _discovery(*args, **kwargs):
        if no_device:
            return {}
        return {
            MAC_ADDRESS: SwidgetDiscoveredDevice(
                MAC_ADDRESS, IP_ADDRESS, FRIENDLY_NAME, SwidgetDimmer, "USB"
            )
        }

    return patch("homeassistant.components.swidget.discover_devices", new=_discovery)


def _patch_single_discovery(device=None, no_device=False):
    async def _discover_single(*args, **kwargs):
        if no_device:
            raise SwidgetException
        return device if device else _mocked_dimmer()

    return patch(
        "homeassistant.components.swidget.discover_single", new=_discover_single
    )


def _patch_connect(device=None, no_device=False):
    async def _connect(*args, **kwargs):
        if no_device:
            raise SwidgetException
        return device if device else _mocked_dimmer()

    return patch("homeassistant.components.swidget.SwidgetDevice.connect", new=_connect)


async def initialize_config_entry_for_device(
    hass: HomeAssistant, dev: SwidgetDevice
) -> MockConfigEntry:
    """Create a mocked configuration entry for the given device.

    Note, the rest of the tests should probably be converted over to use this
    instead of repeating the initialization routine for each test separately
    """
    config_entry = MockConfigEntry(
        title="Swidget",
        domain=DOMAIN,
        unique_id=dev.mac_address,
        data={CONF_HOST: dev.ip_address},
    )
    config_entry.add_to_hass(hass)

    with (
        _patch_discovery(device=dev),
        _patch_single_discovery(device=dev),
        _patch_connect(device=dev),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
