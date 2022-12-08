"""Component for interacting with a Lutron Caseta system."""
from __future__ import annotations

import asyncio
import contextlib
from itertools import chain
import logging
import ssl
from typing import Any, cast

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
    ATTR_BUTTON_TYPE,
    ATTR_DEVICE_NAME,
    ATTR_LEAP_BUTTON_NUMBER,
    ATTR_SERIAL,
    ATTR_TYPE,
    BRIDGE_DEVICE_ID,
    BRIDGE_TIMEOUT,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    CONF_SUBTYPE,
    CONFIG_URL,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
    MANUFACTURER,
    UNASSIGNED_AREA,
)
from .device_trigger import (
    DEVICE_TYPE_SUBTYPE_MAP_TO_LIP,
    KEYPAD_LEAP_BUTTON_NAME_OVERRIDE,
    LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP,
    LUTRON_BUTTON_TRIGGER_SCHEMA,
)
from .models import (
    LUTRON_BUTTON_LEAP_BUTTON_NUMBER,
    LUTRON_KEYPAD_AREA_NAME,
    LUTRON_KEYPAD_BUTTONS,
    LUTRON_KEYPAD_DEVICE_REGISTRY_DEVICE_ID,
    LUTRON_KEYPAD_LUTRON_DEVICE_ID,
    LUTRON_KEYPAD_MODEL,
    LUTRON_KEYPAD_NAME,
    LUTRON_KEYPAD_SERIAL,
    LUTRON_KEYPAD_TYPE,
    LutronButton,
    LutronCasetaData,
    LutronKeypad,
    LutronKeypadData,
)
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
    Platform.BUTTON,
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

    bridge_devices = bridge.get_devices()
    bridge_device = bridge_devices[BRIDGE_DEVICE_ID]

    if not config_entry.unique_id:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=serial_to_unique_id(bridge_device["serial"])
        )

    _async_register_bridge_device(hass, entry_id, bridge_device, bridge)

    keypad_data = _async_setup_keypads(hass, entry_id, bridge, bridge_device)

    # Store this bridge (keyed by entry_id) so it can be retrieved by the
    # platforms we're setting up.

    hass.data[DOMAIN][entry_id] = LutronCasetaData(
        bridge,
        bridge_device,
        keypad_data,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


@callback
def _async_register_bridge_device(
    hass: HomeAssistant, config_entry_id: str, bridge_device: dict, bridge: Smartbridge
) -> None:
    """Register the bridge device in the device registry."""
    device_registry = dr.async_get(hass)

    device_args: DeviceInfo = {
        "name": bridge_device["name"],
        "manufacturer": MANUFACTURER,
        "identifiers": {(DOMAIN, bridge_device["serial"])},
        "model": f"{bridge_device['model']} ({bridge_device['type']})",
        "via_device": (DOMAIN, bridge_device["serial"]),
        "configuration_url": "https://device-login.lutron.com",
    }

    area = _area_name_from_id(bridge.areas, bridge_device["area"])
    if area != UNASSIGNED_AREA:
        device_args["suggested_area"] = area

    device_registry.async_get_or_create(**device_args, config_entry_id=config_entry_id)


@callback
def _async_setup_keypads(
    hass: HomeAssistant,
    config_entry_id: str,
    bridge: Smartbridge,
    bridge_device: dict[str, str | int],
) -> LutronKeypadData:
    """Register keypad devices (Keypads and Pico Remotes) in the device registry."""

    device_registry = dr.async_get(hass)

    bridge_devices: dict[str, dict[str, str | int]] = bridge.get_devices()
    bridge_buttons: dict[str, dict[str, str | int]] = bridge.buttons

    dr_device_id_to_keypad: dict[str, LutronKeypad] = {}
    keypads: dict[int, LutronKeypad] = {}
    keypad_buttons: dict[int, LutronButton] = {}
    keypad_button_names_to_leap: dict[int, dict[str, int]] = {}
    leap_to_keypad_button_names: dict[int, dict[int, str]] = {}

    for bridge_button in bridge_buttons.values():

        parent_device = cast(str, bridge_button["parent_device"])
        bridge_keypad = bridge_devices[parent_device]
        keypad_lutron_device_id = cast(int, bridge_keypad["device_id"])
        button_lutron_device_id = cast(int, bridge_button["device_id"])
        leap_button_number = cast(int, bridge_button["button_number"])
        button_led_device_id = None
        if "button_led" in bridge_button:
            button_led_device_id = cast(str, bridge_button["button_led"])

        if not (keypad := keypads.get(keypad_lutron_device_id)):
            # First time seeing this keypad, build keypad data and store in keypads
            keypad = keypads[keypad_lutron_device_id] = _async_build_lutron_keypad(
                bridge, bridge_device, bridge_keypad, keypad_lutron_device_id
            )

            # Register the keypad device
            dr_device = device_registry.async_get_or_create(
                **keypad["device_info"], config_entry_id=config_entry_id
            )
            keypad[LUTRON_KEYPAD_DEVICE_REGISTRY_DEVICE_ID] = dr_device.id
            dr_device_id_to_keypad[dr_device.id] = keypad

        button_name = _get_button_name(keypad, bridge_button)
        keypad_lutron_device_id = keypad[LUTRON_KEYPAD_LUTRON_DEVICE_ID]

        # Add button to parent keypad, and build keypad_buttons and keypad_button_names_to_leap
        keypad_buttons[button_lutron_device_id] = LutronButton(
            lutron_device_id=button_lutron_device_id,
            leap_button_number=leap_button_number,
            button_name=button_name,
            led_device_id=button_led_device_id,
            parent_keypad=keypad_lutron_device_id,
        )

        keypad[LUTRON_KEYPAD_BUTTONS].append(button_lutron_device_id)

        button_name_to_leap = keypad_button_names_to_leap.setdefault(
            keypad_lutron_device_id, {}
        )
        button_name_to_leap[button_name] = leap_button_number
        leap_to_button_name = leap_to_keypad_button_names.setdefault(
            keypad_lutron_device_id, {}
        )
        leap_to_button_name[leap_button_number] = button_name

    keypad_trigger_schemas = _async_build_trigger_schemas(keypad_button_names_to_leap)

    _async_subscribe_keypad_events(
        hass=hass,
        bridge=bridge,
        keypads=keypads,
        keypad_buttons=keypad_buttons,
        leap_to_keypad_button_names=leap_to_keypad_button_names,
    )

    return LutronKeypadData(
        dr_device_id_to_keypad,
        keypads,
        keypad_buttons,
        keypad_button_names_to_leap,
        keypad_trigger_schemas,
    )


@callback
def _async_build_trigger_schemas(
    keypad_button_names_to_leap: dict[int, dict[str, int]]
) -> dict[int, vol.Schema]:
    """Build device trigger schemas."""

    return {
        keypad_id: LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
            {
                vol.Required(CONF_SUBTYPE): vol.In(
                    keypad_button_names_to_leap[keypad_id]
                ),
            }
        )
        for keypad_id in keypad_button_names_to_leap
    }


@callback
def _async_build_lutron_keypad(
    bridge: Smartbridge,
    bridge_device: dict[str, Any],
    bridge_keypad: dict[str, Any],
    keypad_device_id: int,
) -> LutronKeypad:
    # First time seeing this keypad, build keypad data and store in keypads
    area_name = _area_name_from_id(bridge.areas, bridge_keypad["area"])
    keypad_name = bridge_keypad["name"].split("_")[-1]
    keypad_serial = _handle_none_keypad_serial(bridge_keypad, bridge_device["serial"])
    device_info = DeviceInfo(
        name=f"{area_name} {keypad_name}",
        manufacturer=MANUFACTURER,
        identifiers={(DOMAIN, keypad_serial)},
        model=f"{bridge_keypad['model']} ({bridge_keypad['type']})",
        via_device=(DOMAIN, bridge_device["serial"]),
    )
    if area_name != UNASSIGNED_AREA:
        device_info["suggested_area"] = area_name

    return LutronKeypad(
        lutron_device_id=keypad_device_id,
        dr_device_id="",
        area_id=bridge_keypad["area"],
        area_name=area_name,
        name=keypad_name,
        serial=keypad_serial,
        device_info=device_info,
        model=bridge_keypad["model"],
        type=bridge_keypad["type"],
        buttons=[],
    )


def _get_button_name(keypad: LutronKeypad, bridge_button: dict[str, Any]) -> str:
    """Get the LEAP button name and check for override."""

    button_number = bridge_button["button_number"]
    button_name = bridge_button.get("device_name")

    if button_name is None:
        # This is a Caseta Button retrieve name from hardcoded trigger definitions.
        return _get_button_name_from_triggers(keypad, button_number)

    keypad_model = keypad[LUTRON_KEYPAD_MODEL]
    if keypad_model_override := KEYPAD_LEAP_BUTTON_NAME_OVERRIDE.get(keypad_model):
        if alt_button_name := keypad_model_override.get(button_number):
            return alt_button_name

    return button_name


def _get_button_name_from_triggers(keypad: LutronKeypad, button_number: int) -> str:
    """Retrieve the caseta button name from device triggers."""
    button_number_map = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(keypad["type"], {})
    return (
        button_number_map.get(
            button_number,
            f"button {button_number}",
        )
        .replace("_", " ")
        .title()
    )


def _handle_none_keypad_serial(keypad_device: dict, bridge_serial: int) -> str:
    return keypad_device["serial"] or f"{bridge_serial}_{keypad_device['device_id']}"


def _area_name_from_id(areas: dict[str, dict], area_id: str | None) -> str:
    """Return the full area name including parent(s)."""
    if area_id is None:
        return UNASSIGNED_AREA
    return _construct_area_name_from_id(areas, area_id, [])


def _construct_area_name_from_id(
    areas: dict[str, dict], area_id: str, labels: list[str]
) -> str:
    """Recursively construct the full area name including parent(s)."""
    area = areas[area_id]
    parent_area_id = area["parent_id"]
    if parent_area_id is None:
        # This is the root area, return last area
        return " ".join(labels)

    labels.insert(0, area["name"])
    return _construct_area_name_from_id(areas, parent_area_id, labels)


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
def _async_subscribe_keypad_events(
    hass: HomeAssistant,
    bridge: Smartbridge,
    keypads: dict[int, LutronKeypad],
    keypad_buttons: dict[int, LutronButton],
    leap_to_keypad_button_names: dict[int, dict[int, str]],
):
    """Subscribe to lutron events."""

    @callback
    def _async_button_event(button_id, event_type):
        if not (button := keypad_buttons.get(button_id)) or not (
            keypad := keypads.get(button["parent_keypad"])
        ):
            return

        if event_type == BUTTON_STATUS_PRESSED:
            action = ACTION_PRESS
        else:
            action = ACTION_RELEASE

        keypad_type = keypad[LUTRON_KEYPAD_TYPE]
        keypad_device_id = keypad[LUTRON_KEYPAD_LUTRON_DEVICE_ID]
        leap_button_number = button[LUTRON_BUTTON_LEAP_BUTTON_NUMBER]
        lip_button_number = async_get_lip_button(keypad_type, leap_button_number)
        button_type = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(
            keypad_type, leap_to_keypad_button_names[keypad_device_id]
        )[leap_button_number]

        hass.bus.async_fire(
            LUTRON_CASETA_BUTTON_EVENT,
            {
                ATTR_SERIAL: keypad[LUTRON_KEYPAD_SERIAL],
                ATTR_TYPE: keypad_type,
                ATTR_BUTTON_NUMBER: lip_button_number,
                ATTR_LEAP_BUTTON_NUMBER: leap_button_number,
                ATTR_DEVICE_NAME: keypad[LUTRON_KEYPAD_NAME],
                ATTR_DEVICE_ID: keypad[LUTRON_KEYPAD_DEVICE_REGISTRY_DEVICE_ID],
                ATTR_AREA_NAME: keypad[LUTRON_KEYPAD_AREA_NAME],
                ATTR_BUTTON_TYPE: button_type,
                ATTR_ACTION: action,
            },
        )

    for button_id in keypad_buttons:
        bridge.add_button_subscriber(
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

    def __init__(self, device: dict[str, Any], data: LutronCasetaData) -> None:
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

        if "parent_device" in device:
            # This is a child entity, handle the naming in button.py and switch.py
            return
        area = _area_name_from_id(self._smartbridge.areas, device["area"])
        name = device["name"].split("_")[-1]
        self._attr_name = full_name = f"{area} {name}"
        info = DeviceInfo(
            # Historically we used the device serial number for the identifier
            # but the serial is usually an integer and a string is expected
            # here. Since it would be a breaking change to change the identifier
            # we are ignoring the type error here until it can be migrated to
            # a string in a future release.
            identifiers={(DOMAIN, self._handle_none_serial(self.serial))},  # type: ignore[arg-type]
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

    def _handle_none_serial(self, serial: str | int | None) -> str | int:
        """Handle None serial returned by RA3 and QSX processors."""
        if serial is None:
            return f"{self._bridge_unique_id}_{self.device_id}"
        return serial

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["device_id"]

    @property
    def serial(self) -> int | None:
        """Return the serial number of the device."""
        return self._device["serial"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device (serial)."""
        return str(self._handle_none_serial(self.serial))

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "device_id": self.device_id,
        }
        if zone := self._device.get("zone"):
            attributes["zone_id"] = zone
        return attributes


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
