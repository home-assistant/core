"""Component for interacting with a Lutron Caseta system."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl

import async_timeout
from pylutron_caseta import BUTTON_STATUS_PRESSED
from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType

from .const import (
    ACTION_PRESS,
    ACTION_RELEASE,
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_BUTTON_NUMBER,
    ATTR_DEVICE_NAME,
    ATTR_LEAP_BUTTON_NUMBER,
    ATTR_SERIAL,
    ATTR_TYPE,
    BRIDGE_DEVICE,
    BRIDGE_DEVICE_ID,
    BRIDGE_LEAP,
    BRIDGE_TIMEOUT,
    BUTTON_DEVICES,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
    MANUFACTURER,
)
from .device_trigger import (
    DEVICE_TYPE_SUBTYPE_MAP_TO_LIP,
    LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP,
)

_LOGGER = logging.getLogger(__name__)

DATA_BRIDGE_CONFIG = "lutron_caseta_bridges"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_KEYFILE): cv.string,
                    vol.Required(CONF_CERTFILE): cv.string,
                    vol.Required(CONF_CA_CERTS): cv.string,
                }
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up the Lutron component."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in base_config:
        bridge_configs = base_config[DOMAIN]
        for config in bridge_configs:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    # extract the config keys one-by-one just to be explicit
                    data={
                        CONF_HOST: config[CONF_HOST],
                        CONF_KEYFILE: config[CONF_KEYFILE],
                        CONF_CERTFILE: config[CONF_CERTFILE],
                        CONF_CA_CERTS: config[CONF_CA_CERTS],
                    },
                )
            )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up a bridge from a config entry."""
    entry_id = config_entry.entry_id
    host = config_entry.data[CONF_HOST]
    keyfile = hass.config.path(config_entry.data[CONF_KEYFILE])
    certfile = hass.config.path(config_entry.data[CONF_CERTFILE])
    ca_certs = hass.config.path(config_entry.data[CONF_CA_CERTS])
    bridge = None

    try:
        bridge = Smartbridge.create_tls(
            hostname=host, keyfile=keyfile, certfile=certfile, ca_certs=ca_certs
        )
    except ssl.SSLError:
        _LOGGER.error("Invalid certificate used to connect to bridge at %s", host)
        return False

    timed_out = True
    with contextlib.suppress(asyncio.TimeoutError):
        async with async_timeout.timeout(BRIDGE_TIMEOUT):
            await bridge.connect()
            timed_out = False

    if timed_out or not bridge.is_connected():
        await bridge.close()
        if timed_out:
            raise ConfigEntryNotReady(f"Timed out while trying to connect to {host}")
        if not bridge.is_connected():
            raise ConfigEntryNotReady(f"Cannot connect to {host}")

    _LOGGER.debug("Connected to Lutron Caseta bridge via LEAP at %s", host)

    devices = bridge.get_devices()
    bridge_device = devices[BRIDGE_DEVICE_ID]
    buttons = bridge.buttons
    _async_register_bridge_device(hass, entry_id, bridge_device)
    button_devices = _async_register_button_devices(
        hass, entry_id, bridge_device, buttons
    )
    _async_subscribe_pico_remote_events(hass, bridge, buttons)

    # Store this bridge (keyed by entry_id) so it can be retrieved by the
    # platforms we're setting up.
    hass.data[DOMAIN][entry_id] = {
        BRIDGE_LEAP: bridge,
        BRIDGE_DEVICE: bridge_device,
        BUTTON_DEVICES: button_devices,
    }

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


@callback
def _async_register_bridge_device(
    hass: HomeAssistant, config_entry_id: str, bridge_device: dict
) -> None:
    """Register the bridge device in the device registry."""
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        name=bridge_device["name"],
        manufacturer=MANUFACTURER,
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, bridge_device["serial"])},
        model=f"{bridge_device['model']} ({bridge_device['type']})",
        configuration_url="https://device-login.lutron.com",
    )


@callback
def _async_register_button_devices(
    hass: HomeAssistant,
    config_entry_id: str,
    bridge_device,
    button_devices_by_id: dict[int, dict],
) -> dict[str, dr.DeviceEntry]:
    """Register button devices (Pico Remotes) in the device registry."""
    device_registry = dr.async_get(hass)
    button_devices_by_dr_id = {}
    seen = set()

    for device in button_devices_by_id.values():
        if "serial" not in device or device["serial"] in seen:
            continue
        seen.add(device["serial"])

        dr_device = device_registry.async_get_or_create(
            name=device["name"],
            suggested_area=device["name"].split("_")[0],
            manufacturer=MANUFACTURER,
            config_entry_id=config_entry_id,
            identifiers={(DOMAIN, device["serial"])},
            model=f"{device['model']} ({device['type']})",
            via_device=(DOMAIN, bridge_device["serial"]),
        )

        button_devices_by_dr_id[dr_device.id] = device

    return button_devices_by_dr_id


@callback
def _async_subscribe_pico_remote_events(
    hass: HomeAssistant,
    bridge_device: Smartbridge,
    button_devices_by_id: dict[int, dict],
):
    """Subscribe to lutron events."""

    @callback
    def _async_button_event(button_id, event_type):
        device = button_devices_by_id.get(button_id)

        if not device:
            return

        if event_type == BUTTON_STATUS_PRESSED:
            action = ACTION_PRESS
        else:
            action = ACTION_RELEASE

        type_ = device["type"]
        area, name = device["name"].split("_", 1)
        button_number = device["button_number"]
        # The original implementation used LIP instead of LEAP
        # so we need to convert the button number to maintain compat
        sub_type_to_lip_button = DEVICE_TYPE_SUBTYPE_MAP_TO_LIP[type_]
        leap_button_to_sub_type = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP[type_]
        if (sub_type := leap_button_to_sub_type.get(button_number)) is None:
            _LOGGER.error(
                "Unknown LEAP button number %s is not in %s for %s (%s)",
                button_number,
                leap_button_to_sub_type,
                name,
                type_,
            )
            return
        lip_button_number = sub_type_to_lip_button[sub_type]

        hass.bus.async_fire(
            LUTRON_CASETA_BUTTON_EVENT,
            {
                ATTR_SERIAL: device["serial"],
                ATTR_TYPE: type_,
                ATTR_BUTTON_NUMBER: lip_button_number,
                ATTR_LEAP_BUTTON_NUMBER: button_number,
                ATTR_DEVICE_NAME: name,
                ATTR_AREA_NAME: area,
                ATTR_ACTION: action,
            },
        )

    for button_id in button_devices_by_id:
        bridge_device.add_button_subscriber(
            str(button_id),
            lambda event_type, button_id=button_id: _async_button_event(
                button_id, event_type
            ),
        )


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload the bridge bridge from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    smartbridge: Smartbridge = data[BRIDGE_LEAP]
    await smartbridge.close()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class LutronCasetaDevice(Entity):
    """Common base class for all Lutron Caseta devices."""

    def __init__(self, device, bridge, bridge_device):
        """Set up the base class.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        [:param]bridge_device a dict with the details of the bridge
        """
        self._device = device
        self._smartbridge = bridge
        self._bridge_device = bridge_device

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_subscriber(self.device_id, self.async_write_ha_state)

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["device_id"]

    @property
    def name(self):
        """Return the name of the device."""
        return self._device["name"]

    @property
    def serial(self):
        """Return the serial number of the device."""
        return self._device["serial"]

    @property
    def unique_id(self):
        """Return the unique ID of the device (serial)."""
        return str(self.serial)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            manufacturer=MANUFACTURER,
            model=f"{self._device['model']} ({self._device['type']})",
            name=self.name,
            suggested_area=self._device["name"].split("_")[0],
            via_device=(DOMAIN, self._bridge_device["serial"]),
            configuration_url="https://device-login.lutron.com",
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id, "zone_id": self._device["zone"]}

    @property
    def should_poll(self):
        """No polling needed."""
        return False
