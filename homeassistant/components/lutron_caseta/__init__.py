"""Component for interacting with a Lutron Caseta system."""
import asyncio
import logging

from aiolip import LIP
from aiolip.data import LIPMode
from aiolip.protocol import LIP_BUTTON_PRESS, LIP_BUTTON_RELEASE
from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    LUTRON_CASETA_BUTTON_EVENT,
    LUTRON_CASETA_LEAP,
    LUTRON_CASETA_LIP,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "lutron_caseta"
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

LUTRON_CASETA_COMPONENTS = ["light", "switch", "cover", "scene", "fan", "binary_sensor"]


async def async_setup(hass, base_config):
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


async def async_setup_entry(hass, config_entry):
    """Set up a bridge from a config entry."""

    host = config_entry.data[CONF_HOST]
    keyfile = hass.config.path(config_entry.data[CONF_KEYFILE])
    certfile = hass.config.path(config_entry.data[CONF_CERTFILE])
    ca_certs = hass.config.path(config_entry.data[CONF_CA_CERTS])

    bridge = Smartbridge.create_tls(
        hostname=host, keyfile=keyfile, certfile=certfile, ca_certs=ca_certs
    )

    await bridge.connect()
    if not bridge.is_connected():
        _LOGGER.error("Unable to connect to Lutron Caseta bridge at %s", host)
        raise ConfigEntryNotReady

    _LOGGER.debug("Connected to Lutron Caseta bridge via LEAP at %s", host)

    # Store this bridge (keyed by entry_id) so it can be retrieved by the
    # components we're setting up.
    data = hass.data[DOMAIN][config_entry.entry_id] = {
        LUTRON_CASETA_LEAP: bridge,
        LUTRON_CASETA_LIP: None,
    }

    lip_devices = bridge.get_lip_devices()
    if lip_devices:
        # If the bridge also supports LIP (Lutron Integration Protocol)
        # we can fire events when pico buttons are pressed to allow
        # pico remotes to control other devices.
        lip = LIP()
        try:
            await lip.async_connect(host)
        except asyncio.TimeoutError:
            _LOGGER.error("Failed to connect to via LIP at %s:23", host)
            pass
        else:
            _LOGGER.debug("Connected to Lutron Caseta bridge via LIP at %s:23", host)
            data[LUTRON_CASETA_LIP] = lip
            button_devices_by_id = await _async_merge_lip_leap_data(lip_devices, bridge)
            await _async_register_button_devices(
                hass, config_entry.entry_id, button_devices_by_id
            )
            _async_subscribe_pico_remote_events(hass, lip, button_devices_by_id)

    for component in LUTRON_CASETA_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


@callback
def _async_merge_lip_leap_data(lip_devices, bridge):
    """Merge the leap data into the lip data."""
    sensor_devices = bridge.get_devices_by_domain("sensor")

    button_devices_by_id = {
        id: device for id, device in lip_devices.items() if "Buttons" in device
    }
    sensor_devices_by_name = {device["name"]: device for device in sensor_devices}

    # Add the leap data into the lip data
    # so we know the type, model, and serial
    for device in button_devices_by_id.values():
        area = device.get("Area", {}).get("Name", "")
        name = device["Name"]
        leap_name = f"{area}_{name}"
        leap_device_data = sensor_devices_by_name.get(leap_name)
        if leap_device_data is None:
            continue
        for key in ("type", "model", "serial"):
            val = leap_device_data.get(key)
            if val is not None:
                device[key] = val

    _LOGGER.debug("Button Devices: %s", button_devices_by_id)


async def _async_register_button_devices(hass, config_entry_id, button_devices_by_id):
    """Register button devices (Pico Remotes) in the device registry."""
    device_registry = await dr.async_get_registry(hass)

    for device in button_devices_by_id.values():
        if "serial" not in device:
            continue

        device_entry = {
            "name": device["Name"],
            "manufacturer": MANUFACTURER,
            "config_entry_id": config_entry_id,
            "identifiers": {(DOMAIN, device["serial"])},
        }

        if "model" in device:
            device_entry["model"] = device["model"]

        device_registry.async_get_or_create(**device_entry)

    return button_devices_by_id


@callback
def _async_subscribe_pico_remote_events(hass, lip, button_devices_by_id):
    """Subscribe to lutron events."""

    @callback
    def _async_lip_event(lip_message):
        if lip_message.mode != LIPMode.DEVICE:
            return

        device = button_devices_by_id.get(lip_message.integration_id)

        if not device:
            return

        hass.bus.async_fire(
            LUTRON_CASETA_BUTTON_EVENT,
            {
                "device_id": lip_message.integration_id,
                "serial": device.get("serial"),
                "type": device.get("type"),
                "model": device.get("model"),
                "button_number": lip_message.action_number,
                "device_name": device["Name"],
                "area_name": device.get("Area", {}).get("Name"),
                "press": lip_message.value == LIP_BUTTON_PRESS,
                "release": lip_message.value == LIP_BUTTON_RELEASE,
            },
        )

    lip.subscribe(_async_lip_event)

    asyncio.create_task(lip.async_run())


async def async_unload_entry(hass, config_entry):
    """Unload the bridge bridge from a config entry."""

    data = hass.data[DOMAIN][config_entry.entry_id]
    data[LUTRON_CASETA_LEAP].close()
    if data[LUTRON_CASETA_LIP]:
        await data[LUTRON_CASETA_LIP].async_stop()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in LUTRON_CASETA_COMPONENTS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class LutronCasetaDevice(Entity):
    """Common base class for all Lutron Caseta devices."""

    def __init__(self, device, bridge):
        """Set up the base class.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        """
        self._device = device
        self._smartbridge = bridge

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
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.serial)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": self._device["model"],
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id, "zone_id": self._device["zone"]}

    @property
    def should_poll(self):
        """No polling needed."""
        return False
