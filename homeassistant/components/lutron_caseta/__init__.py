"""Component for interacting with a Lutron Caseta system."""
import asyncio
import logging
import ssl

from aiolip import LIP
from aiolip.data import LIPMode
from aiolip.protocol import LIP_BUTTON_PRESS
import async_timeout
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
    ACTION_PRESS,
    ACTION_RELEASE,
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_BUTTON_NUMBER,
    ATTR_DEVICE_NAME,
    ATTR_SERIAL,
    ATTR_TYPE,
    BRIDGE_DEVICE,
    BRIDGE_DEVICE_ID,
    BRIDGE_LEAP,
    BRIDGE_LIP,
    BRIDGE_TIMEOUT,
    BUTTON_DEVICES,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
    MANUFACTURER,
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

PLATFORMS = ["light", "switch", "cover", "scene", "fan", "binary_sensor"]


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
    bridge = None

    try:
        bridge = Smartbridge.create_tls(
            hostname=host, keyfile=keyfile, certfile=certfile, ca_certs=ca_certs
        )
    except ssl.SSLError:
        _LOGGER.error("Invalid certificate used to connect to bridge at %s", host)
        return False

    timed_out = True
    try:
        async with async_timeout.timeout(BRIDGE_TIMEOUT):
            await bridge.connect()
            timed_out = False
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout while trying to connect to bridge at %s", host)

    if timed_out or not bridge.is_connected():
        await bridge.close()
        raise ConfigEntryNotReady

    _LOGGER.debug("Connected to Lutron Caseta bridge via LEAP at %s", host)

    devices = bridge.get_devices()
    bridge_device = devices[BRIDGE_DEVICE_ID]
    await _async_register_bridge_device(hass, config_entry.entry_id, bridge_device)
    # Store this bridge (keyed by entry_id) so it can be retrieved by the
    # platforms we're setting up.
    hass.data[DOMAIN][config_entry.entry_id] = {
        BRIDGE_LEAP: bridge,
        BRIDGE_DEVICE: bridge_device,
        BUTTON_DEVICES: {},
        BRIDGE_LIP: None,
    }

    if bridge.lip_devices:
        # If the bridge also supports LIP (Lutron Integration Protocol)
        # we can fire events when pico buttons are pressed to allow
        # pico remotes to control other devices.
        await async_setup_lip(hass, config_entry, bridge.lip_devices)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_setup_lip(hass, config_entry, lip_devices):
    """Connect to the bridge via Lutron Integration Protocol to watch for pico remotes."""
    host = config_entry.data[CONF_HOST]
    config_entry_id = config_entry.entry_id
    data = hass.data[DOMAIN][config_entry_id]
    bridge_device = data[BRIDGE_DEVICE]
    bridge = data[BRIDGE_LEAP]
    lip = LIP()
    try:
        await lip.async_connect(host)
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Failed to connect to via LIP at %s:23, Pico and Shade remotes will not be available; "
            "Enable Telnet Support in the Lutron app under Settings >> Advanced >> Integration",
            host,
        )
        return

    _LOGGER.debug("Connected to Lutron Caseta bridge via LIP at %s:23", host)
    button_devices_by_lip_id = _async_merge_lip_leap_data(lip_devices, bridge)
    button_devices_by_dr_id = await _async_register_button_devices(
        hass, config_entry_id, bridge_device, button_devices_by_lip_id
    )
    _async_subscribe_pico_remote_events(hass, lip, button_devices_by_lip_id)
    data[BUTTON_DEVICES] = button_devices_by_dr_id
    data[BRIDGE_LIP] = lip


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
        device["leap_name"] = leap_name
        leap_device_data = sensor_devices_by_name.get(leap_name)
        if leap_device_data is None:
            continue
        for key in ("type", "model", "serial"):
            val = leap_device_data.get(key)
            if val is not None:
                device[key] = val

    _LOGGER.debug("Button Devices: %s", button_devices_by_id)
    return button_devices_by_id


async def _async_register_bridge_device(hass, config_entry_id, bridge_device):
    """Register the bridge device in the device registry."""
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        name=bridge_device["name"],
        manufacturer=MANUFACTURER,
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, bridge_device["serial"])},
        model=f"{bridge_device['model']} ({bridge_device['type']})",
    )


async def _async_register_button_devices(
    hass, config_entry_id, bridge_device, button_devices_by_id
):
    """Register button devices (Pico Remotes) in the device registry."""
    device_registry = await dr.async_get_registry(hass)
    button_devices_by_dr_id = {}

    for device in button_devices_by_id.values():
        if "serial" not in device:
            continue

        dr_device = device_registry.async_get_or_create(
            name=device["leap_name"],
            suggested_area=device["leap_name"].split("_")[0],
            manufacturer=MANUFACTURER,
            config_entry_id=config_entry_id,
            identifiers={(DOMAIN, device["serial"])},
            model=f"{device['model']} ({device['type']})",
            via_device=(DOMAIN, bridge_device["serial"]),
        )

        button_devices_by_dr_id[dr_device.id] = device

    return button_devices_by_dr_id


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

        if lip_message.value == LIP_BUTTON_PRESS:
            action = ACTION_PRESS
        else:
            action = ACTION_RELEASE

        hass.bus.async_fire(
            LUTRON_CASETA_BUTTON_EVENT,
            {
                ATTR_SERIAL: device.get("serial"),
                ATTR_TYPE: device.get("type"),
                ATTR_BUTTON_NUMBER: lip_message.action_number,
                ATTR_DEVICE_NAME: device["Name"],
                ATTR_AREA_NAME: device.get("Area", {}).get("Name"),
                ATTR_ACTION: action,
            },
        )

    lip.subscribe(_async_lip_event)

    asyncio.create_task(lip.async_run())


async def async_unload_entry(hass, config_entry):
    """Unload the bridge bridge from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    data[BRIDGE_LEAP].close()
    if data[BRIDGE_LIP]:
        await data[BRIDGE_LIP].async_stop()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

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
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.serial)},
            "name": self.name,
            "suggested_area": self._device["name"].split("_")[0],
            "manufacturer": MANUFACTURER,
            "model": f"{self._device['model']} ({self._device['type']})",
            "via_device": (DOMAIN, self._bridge_device["serial"]),
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id, "zone_id": self._device["zone"]}

    @property
    def should_poll(self):
        """No polling needed."""
        return False
