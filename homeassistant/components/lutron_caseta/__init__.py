"""Component for interacting with a Lutron Caseta system."""
from __future__ import annotations

import asyncio
import contextlib
from itertools import chain
import logging
import ssl
from typing import Any

import async_timeout
from pylutron_caseta import BUTTON_STATUS_PRESSED
from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_DEVICE_ID, ATTR_SUGGESTED_AREA, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
    BRIDGE_DEVICE_ID,
    BRIDGE_TIMEOUT,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    CONFIG_URL,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
    MANUFACTURER,
    UNASSIGNED_AREA,
)
from .device_trigger import (
    DEVICE_TYPE_SUBTYPE_MAP_TO_LIP,
    LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP,
    _lutron_model_to_device_type,
)
from .models import LutronCasetaData
from .util import serial_to_unique_id

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


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Migrate entities since the occupancygroup were not actually unique."""

    dev_reg = dr.async_get(hass)
    bridge_unique_id = entry.unique_id

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if not (unique_id := entity_entry.unique_id):
            return None
        if not unique_id.startswith("occupancygroup_") or unique_id.startswith(
            f"occupancygroup_{bridge_unique_id}"
        ):
            return None
        sensor_id = unique_id.split("_")[1]
        new_unique_id = f"occupancygroup_{bridge_unique_id}_{sensor_id}"
        if dev_entry := dev_reg.async_get_device({(DOMAIN, unique_id)}):
            dev_reg.async_update_device(
                dev_entry.id, new_identifiers={(DOMAIN, new_unique_id)}
            )
        return {"new_unique_id": f"occupancygroup_{bridge_unique_id}_{sensor_id}"}

    await er.async_migrate_entries(hass, entry.entry_id, _async_migrator)


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
    await _async_migrate_unique_ids(hass, config_entry)

    devices = bridge.get_devices()
    bridge_device = devices[BRIDGE_DEVICE_ID]
    if not config_entry.unique_id:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=serial_to_unique_id(bridge_device["serial"])
        )

    buttons = bridge.buttons
    _async_register_bridge_device(hass, entry_id, bridge_device)
    button_devices, device_info_by_device_id = _async_register_button_devices(
        hass, entry_id, bridge, bridge_device, buttons
    )
    _async_subscribe_pico_remote_events(hass, bridge, buttons)

    # Store this bridge (keyed by entry_id) so it can be retrieved by the
    # platforms we're setting up.
    hass.data[DOMAIN][entry_id] = LutronCasetaData(
        bridge, bridge_device, button_devices, device_info_by_device_id
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

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
    bridge,
    bridge_device,
    button_devices_by_id: dict[int, dict],
) -> tuple[dict[str, dict], dict[int, dict[str, Any]]]:
    """Register button devices (Pico Remotes) in the device registry."""
    device_registry = dr.async_get(hass)
    button_devices_by_dr_id: dict[str, dict] = {}
    device_info_by_device_id: dict[int, dict[str, Any]] = {}
    seen: set[str] = set()
    bridge_devices = bridge.get_devices()

    for device in button_devices_by_id.values():

        ha_device = device
        if "parent_device" in device and device["parent_device"] is not None:
            # Device is a child of parent_device
            # use the parent_device for HA device info
            ha_device = bridge_devices[device["parent_device"]]

        ha_device_serial = _handle_none_keypad_serial(
            ha_device, bridge_device["serial"]
        )

        if "serial" not in ha_device or ha_device_serial in seen:
            continue
        seen.add(ha_device_serial)

        area, name = _area_and_name_from_name(ha_device["name"])
        device_args: dict[str, Any] = {
            "name": f"{area} {name}",
            "manufacturer": MANUFACTURER,
            "config_entry_id": config_entry_id,
            "identifiers": {(DOMAIN, ha_device_serial)},
            "model": f"{ha_device['model']} ({ha_device['type']})",
            "via_device": (DOMAIN, bridge_device["serial"]),
        }
        if area != UNASSIGNED_AREA:
            device_args["suggested_area"] = area

        dr_device = device_registry.async_get_or_create(**device_args)
        button_devices_by_dr_id[dr_device.id] = ha_device
        device_info_by_device_id.setdefault(ha_device["device_id"], device_args)

    return button_devices_by_dr_id, device_info_by_device_id


def _handle_none_keypad_serial(keypad_device: dict, bridge_serial: int) -> str:
    return keypad_device["serial"] or f"{bridge_serial}_{keypad_device['device_id']}"


def _area_and_name_from_name(device_name: str) -> tuple[str, str]:
    """Return the area and name from the devices internal name."""
    if "_" in device_name:
        area_device_name = device_name.split("_", 1)
        return area_device_name[0], area_device_name[1]
    return UNASSIGNED_AREA, device_name


@callback
def async_get_lip_button(device_type: str, leap_button: int) -> int | None:
    """Get the LIP button for a given LEAP button."""
    if (
        lip_buttons_name_to_num := DEVICE_TYPE_SUBTYPE_MAP_TO_LIP.get(device_type)
    ) is None or (
        leap_button_num_to_name := LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(device_type)
    ) is None:
        return None
    return lip_buttons_name_to_num[leap_button_num_to_name[leap_button]]


@callback
def _async_subscribe_pico_remote_events(
    hass: HomeAssistant,
    bridge_device: Smartbridge,
    button_devices_by_id: dict[int, dict],
):
    """Subscribe to lutron events."""
    dev_reg = dr.async_get(hass)

    @callback
    def _async_button_event(button_id, event_type):
        if not (device := button_devices_by_id.get(button_id)):
            return

        if event_type == BUTTON_STATUS_PRESSED:
            action = ACTION_PRESS
        else:
            action = ACTION_RELEASE

        bridge_devices = bridge_device.get_devices()
        ha_device = device
        if "parent_device" in device and device["parent_device"] is not None:
            # Device is a child of parent_device
            # use the parent_device for HA device info
            ha_device = bridge_devices[device["parent_device"]]

        ha_device_serial = _handle_none_keypad_serial(
            ha_device, bridge_devices[BRIDGE_DEVICE_ID]["serial"]
        )

        type_ = _lutron_model_to_device_type(ha_device["model"], ha_device["type"])
        area, name = _area_and_name_from_name(ha_device["name"])
        leap_button_number = device["button_number"]
        lip_button_number = async_get_lip_button(type_, leap_button_number)
        hass_device = dev_reg.async_get_device({(DOMAIN, ha_device_serial)})

        hass.bus.async_fire(
            LUTRON_CASETA_BUTTON_EVENT,
            {
                ATTR_SERIAL: ha_device_serial,
                ATTR_TYPE: type_,
                ATTR_BUTTON_NUMBER: lip_button_number,
                ATTR_LEAP_BUTTON_NUMBER: leap_button_number,
                ATTR_DEVICE_NAME: name,
                ATTR_DEVICE_ID: hass_device.id,
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
    data: LutronCasetaData = hass.data[DOMAIN][entry.entry_id]
    await data.bridge.close()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class LutronCasetaDevice(Entity):
    """Common base class for all Lutron Caseta devices."""

    _attr_should_poll = False

    def __init__(self, device, data):
        """Set up the base class.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        [:param]bridge_device a dict with the details of the bridge
        """
        self._device = device
        self._smartbridge = data.bridge
        self._bridge_device = data.bridge_device
        self._bridge_unique_id = serial_to_unique_id(data.bridge_device["serial"])
        if "serial" not in self._device:
            return

        if "parent_device" in device and (
            parent_device_info := data.device_info_by_device_id.get(
                device["parent_device"]
            )
        ):
            # Append the child device name to the end of the parent keypad name to create the entity name
            self._attr_name = f'{parent_device_info["name"]} {device["device_name"]}'
            # Set the device_info to the same as the Parent Keypad
            # The entities will be nested inside the keypad device
            self._attr_device_info = parent_device_info
            return

        area, name = _area_and_name_from_name(device["name"])
        self._attr_name = full_name = f"{area} {name}"
        info = DeviceInfo(
            identifiers={(DOMAIN, self._handle_none_serial(self.serial))},
            manufacturer=MANUFACTURER,
            model=f"{device['model']} ({device['type']})",
            name=full_name,
            via_device=(DOMAIN, self._bridge_device["serial"]),
            configuration_url=CONFIG_URL,
        )
        if area != UNASSIGNED_AREA:
            info[ATTR_SUGGESTED_AREA] = area
        self._attr_device_info = info

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_subscriber(self.device_id, self.async_write_ha_state)

    def _handle_none_serial(self, serial: str | None) -> str | int:
        """Handle None serial returned by RA3 and QSX processors."""
        if serial is None:
            return f"{self._bridge_unique_id}_{self.device_id}"
        return serial

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["device_id"]

    @property
    def serial(self):
        """Return the serial number of the device."""
        return self._device["serial"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device (serial)."""
        return str(self._handle_none_serial(self.serial))

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id, "zone_id": self._device["zone"]}


class LutronCasetaDeviceUpdatableEntity(LutronCasetaDevice):
    """A lutron_caseta entity that can update by syncing data from the bridge."""

    async def async_update(self) -> None:
        """Update when forcing a refresh of the device."""
        self._device = self._smartbridge.get_device_by_id(self.device_id)
        _LOGGER.debug(self._device)


def _id_to_identifier(lutron_id: str) -> tuple[str, str]:
    """Convert a lutron caseta identifier to a device identifier."""
    return (DOMAIN, lutron_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove lutron_caseta config entry from a device."""
    data: LutronCasetaData = hass.data[DOMAIN][entry.entry_id]
    bridge = data.bridge
    devices = bridge.get_devices()
    buttons = bridge.buttons
    occupancy_groups = bridge.occupancy_groups
    bridge_device = devices[BRIDGE_DEVICE_ID]
    bridge_unique_id = serial_to_unique_id(bridge_device["serial"])
    all_identifiers: set[tuple[str, str]] = {
        # Base bridge
        _id_to_identifier(bridge_unique_id),
        # Motion sensors and occupancy groups
        *(
            _id_to_identifier(
                f"occupancygroup_{bridge_unique_id}_{device['occupancy_group_id']}"
            )
            for device in occupancy_groups.values()
        ),
        # Button devices such as pico remotes and all other devices
        *(
            _id_to_identifier(device["serial"])
            for device in chain(devices.values(), buttons.values())
        ),
    }
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier in all_identifiers
    )
