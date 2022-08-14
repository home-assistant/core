"""Config flow for ZHA."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

import serial.tools.list_ports
import voluptuous as vol
from zigpy.application import ControllerApplication
import zigpy.backups
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.exceptions import NetworkNotFormed

from homeassistant import config_entries
from homeassistant.components import onboarding, usb, zeroconf
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .core.const import (
    CONF_BAUDRATE,
    CONF_DATABASE,
    CONF_FLOWCONTROL,
    CONF_RADIO_TYPE,
    CONF_ZIGPY,
    DATA_ZHA,
    DATA_ZHA_CONFIG,
    DEFAULT_DATABASE_NAME,
    DOMAIN,
    RadioType,
)

CONF_MANUAL_PATH = "Enter Manually"
SUPPORTED_PORT_SETTINGS = (
    CONF_BAUDRATE,
    CONF_FLOWCONTROL,
)
DECONZ_DOMAIN = "deconz"

# Only the common radio types will be autoprobed, ordered by new device popularity.
# XBee takes too long to probe since it scans through all possible bauds and likely has
# very few users to begin with.
AUTOPROBE_RADIOS = (
    RadioType.ezsp,
    RadioType.znp,
    RadioType.deconz,
    RadioType.zigate,
)

FORMATION_STRATEGY = "formation_strategy"
FORMATION_FORM_NEW_NETWORK = "Form a new network"
FORMATION_REUSE_SETTINGS = "Keep current network settings"
FORMATION_RESTORE_AUTOMATIC_BACKUP = "Restore an automatic backup"
FORMATION_RESTORE_MANUAL_BACKUP = "Restore a manual backup"

CHOOSE_AUTOMATIC_BACKUP = "choose_automatic_backup"
OVERWRITE_COORDINATOR_IEEE = "overwrite_coordinator_ieee"

_LOGGER = logging.getLogger(__name__)


class ZhaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 3

    def __init__(self):
        """Initialize flow instance."""
        self._device_path: str | None = None
        self._device_settings: dict[str, Any] | None = None
        self._radio_type: RadioType | None = None
        self._title: str | None = None
        self._current_settings: zigpy.backups.NetworkBackup | None = None
        self._backups: list[zigpy.backups.NetworkBackup] | None = None

    @contextlib.asynccontextmanager
    async def _connect_zigpy_app(self) -> ControllerApplication:
        """Connect to the radio with the current config and then clean up."""
        config = self.hass.data.get(DATA_ZHA, {}).get(DATA_ZHA_CONFIG, {})

        assert self._radio_type is not None

        app_config = config.get(CONF_ZIGPY, {}).copy()
        app_config[CONF_DATABASE] = config.get(
            CONF_DATABASE,
            self.hass.config.path(DEFAULT_DATABASE_NAME),
        )
        app_config[CONF_DEVICE] = self._device_settings
        app_config = self._radio_type.controller.SCHEMA(app_config)

        app = await self._radio_type.controller.new(
            app_config, auto_form=False, start_radio=False
        )

        try:
            await app.connect()
            yield app
        finally:
            await app.disconnect()

    async def _detect_radio_type(self) -> bool:
        """Probe all radio types on the current port."""
        for radio in AUTOPROBE_RADIOS:
            _LOGGER.debug("Attempting to probe radio type %s", radio)

            dev_config = radio.controller.SCHEMA_DEVICE(
                {CONF_DEVICE_PATH: self._device_path}
            )
            probe_result = await radio.controller.probe(dev_config)

            if not probe_result:
                continue

            # Radio library probing can succeed and return new device settings
            if isinstance(probe_result, dict):
                dev_config = probe_result

            self._radio_type = radio
            self._device_settings = dev_config

            return True

        return False

    async def _async_create_radio_entity(self):
        device_settings = self._device_settings.copy()
        device_settings[CONF_DEVICE_PATH] = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, self._device_path
        )

        return self.async_create_entry(
            title=self._title,
            data={CONF_DEVICE: device_settings, CONF_RADIO_TYPE: self._radio_type.name},
        )

    async def async_step_user(self, user_input=None):
        """Handle a zha config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]

        if not list_of_ports:
            return await self.async_step_manual_pick_radio_type()

        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_DEVICE_PATH]

            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_manual_pick_radio_type()

            port = ports[list_of_ports.index(user_selection)]
            self._device_path = port.device

            if not await self._detect_radio_type():
                # Did not autodetect anything, proceed to manual selection
                return await self.async_step_manual_pick_radio_type()

            self._title = (
                f"{port.description}, s/n: {port.serial_number or 'n/a'}"
                f" - {port.manufacturer}"
                if port.manufacturer
                else ""
            )

            return await self.async_step_choose_formation_strategy()

        schema = vol.Schema({vol.Required(CONF_DEVICE_PATH): vol.In(list_of_ports)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_manual_pick_radio_type(self, user_input=None):
        """Manually select radio type."""

        if user_input is not None:
            self._radio_type = RadioType.get_by_description(user_input[CONF_RADIO_TYPE])
            return await self.async_step_manual_port_config()

        schema = {vol.Required(CONF_RADIO_TYPE): vol.In(RadioType.list())}
        return self.async_show_form(
            step_id="manual_pick_radio_type",
            data_schema=vol.Schema(schema),
        )

    async def async_step_manual_port_config(self, user_input=None):
        """Enter port settings specific for this type of radio."""
        errors = {}
        app_cls = self._radio_type.controller

        if user_input is not None:
            self._device_path = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input[CONF_DEVICE_PATH]
            )
            self._device_settings = {
                k: v for k, v in user_input.items() if k != CONF_DEVICE_PATH
            }

            if await app_cls.probe(user_input):
                return await self._async_create_radio_entity()

            errors["base"] = "cannot_connect"

        schema = {
            vol.Required(
                CONF_DEVICE_PATH, default=self._device_path or vol.UNDEFINED
            ): str
        }

        source = self.context.get("source")
        for param, value in app_cls.SCHEMA_DEVICE.schema.items():
            if param in SUPPORTED_PORT_SETTINGS:
                schema[param] = value
                if source == config_entries.SOURCE_ZEROCONF and param == CONF_BAUDRATE:
                    schema[param] = 115200

        return self.async_show_form(
            step_id="manual_port_config",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_choose_formation_strategy(self, user_input=None):
        """Choose how to deal with the current radio's settings."""

        if user_input is not None:
            strategy = user_input[FORMATION_STRATEGY]

            if strategy == FORMATION_FORM_NEW_NETWORK:
                async with self._connect_zigpy_app() as app:
                    await app.form_network()
            elif strategy == FORMATION_REUSE_SETTINGS:
                pass
            elif strategy == FORMATION_RESTORE_MANUAL_BACKUP:
                raise NotImplementedError("Not implemented yet :(")
            elif strategy == FORMATION_RESTORE_AUTOMATIC_BACKUP:
                return await self.async_step_restore_automatic_backup()

            return await self._async_create_radio_entity()

        suggested_strategy = FORMATION_FORM_NEW_NETWORK

        async with self._connect_zigpy_app() as app:
            strategies = [
                FORMATION_FORM_NEW_NETWORK,
            ]

            # Check if the stick has any settings
            try:
                await app.load_network_info()
            except NetworkNotFormed:
                pass
            else:
                # Load the current info while were'c onnected, to save time
                self._backups = app.backups.backups.copy()
                self._current_settings = zigpy.backups.NetworkBackup(
                    network_info=app.state.network_info,
                    node_info=app.state.node_info,
                )
                strategies.append(FORMATION_REUSE_SETTINGS)
                suggested_strategy = FORMATION_REUSE_SETTINGS

            strategies.append(FORMATION_RESTORE_MANUAL_BACKUP)

            # Check if we have any automatic backups
            if app.backups.backups:
                strategies.append(FORMATION_RESTORE_AUTOMATIC_BACKUP)
                suggested_strategy = FORMATION_RESTORE_AUTOMATIC_BACKUP

        schema = {
            vol.Required(FORMATION_STRATEGY, default=suggested_strategy): vol.In(
                strategies
            ),
        }

        return self.async_show_form(
            step_id="choose_formation_strategy",
            data_schema=vol.Schema(schema),
        )

    async def async_step_restore_automatic_backup(self, user_input=None):
        """Select and restore an automatic backup."""

        if self._backups is None or self._current_settings is None:
            async with self._connect_zigpy_app() as app:
                try:
                    self._current_settings = app.backups.create_backup(
                        load_devices=True
                    )
                except NetworkNotFormed:
                    self._current_settings = None

                self._backups = app.backups.backups

        choices = [
            (
                f"{b.backup_time.strftime('%c')}"
                f" (PAN ID: {b.network_info.pan_id}"
                f", EPID: {b.network_info.extended_pan_id})"
            )
            for b in self._backups
        ]

        if user_input is not None:
            backup = self._backups[choices.index(user_input[CHOOSE_AUTOMATIC_BACKUP])]

            if user_input.get(OVERWRITE_COORDINATOR_IEEE):
                backup.network_info.stack_specific.setdefault("ezsp", {})[
                    "i_understand_i_can_update_eui64_only_once"
                    "_and_i_still_want_to_do_it"
                ] = True

            async with self._connect_zigpy_app() as app:
                app.backups.restore_backup(backup)

            return await self._async_create_radio_entity()

        data_schema = {
            vol.Required(CHOOSE_AUTOMATIC_BACKUP, default=choices[0]): vol.In(choices),
        }

        # Only allow the IEEE to be written when the radio type is EZSP
        if self._radio_type == RadioType.ezsp and (
            self._current_settings is None
            or any(
                backup.node_info.ieee != self._current_settings.node_info.ieee
                for backup in self._backups
            )
        ):
            data_schema[vol.Required(OVERWRITE_COORDINATOR_IEEE, default=True)] = bool

        return self.async_show_form(
            step_id="restore_automatic_backup",
            data_schema=vol.Schema(data_schema),
        )

    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo) -> FlowResult:
        """Handle usb discovery."""
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        device = discovery_info.device
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, device)
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"
        if current_entry := await self.async_set_unique_id(unique_id):
            self._abort_if_unique_id_configured(
                updates={
                    CONF_DEVICE: {
                        **current_entry.data.get(CONF_DEVICE, {}),
                        CONF_DEVICE_PATH: dev_path,
                    },
                }
            )
        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # If they already have a discovery for deconz we ignore the usb discovery as
        # they probably want to use it there instead
        if self.hass.config_entries.flow.async_progress_by_handler(DECONZ_DOMAIN):
            return self.async_abort(reason="not_zha_device")
        for entry in self.hass.config_entries.async_entries(DECONZ_DOMAIN):
            if entry.source != config_entries.SOURCE_IGNORE:
                return self.async_abort(reason="not_zha_device")

        self._device_path = dev_path
        self._title = description or usb.human_readable_device_name(
            dev_path,
            serial_number,
            manufacturer,
            description,
            vid,
            pid,
        )
        self._set_confirm_only()
        self.context["title_placeholders"] = {CONF_NAME: self._title}
        return await self.async_step_usb_confirm()

    async def async_step_confirm_usb(self, user_input=None):
        """Confirm a discovery."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            if not await self._detect_radio_type():
                # This path probably will not happen now that we have
                # more precise USB matching unless there is a problem
                # with the device
                return self.async_abort(reason="usb_probe_failed")

            return await self.async_step_choose_formation_strategy()

        return self.async_show_form(
            step_id="confirm_usb",
            description_placeholders={CONF_NAME: self._title},
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        # Hostname is format: livingroom.local.
        local_name = discovery_info.hostname[:-1]
        radio_type = discovery_info.properties.get("radio_type") or local_name
        node_name = local_name[: -len(".local")]
        host = discovery_info.host
        port = discovery_info.port
        if local_name.startswith("tube") or "efr32" in local_name:
            # This is hard coded to work with legacy devices
            port = 6638
        device_path = f"socket://{host}:{port}"

        if current_entry := await self.async_set_unique_id(node_name):
            self._abort_if_unique_id_configured(
                updates={
                    CONF_DEVICE: {
                        **current_entry.data.get(CONF_DEVICE, {}),
                        CONF_DEVICE_PATH: device_path,
                    },
                }
            )

        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self.context["title_placeholders"] = {CONF_NAME: node_name}
        self._device_path = device_path

        if "efr32" in radio_type:
            self._radio_type = RadioType.ezsp
        elif "zigate" in radio_type:
            self._radio_type = RadioType.zigate
        else:
            self._radio_type = RadioType.znp

        return await self.async_step_manual_port_config()

    async def async_step_hardware(self, data=None):
        """Handle hardware flow."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if not data:
            return self.async_abort(reason="invalid_hardware_data")
        if data.get("radio_type") != "efr32":
            return self.async_abort(reason="invalid_hardware_data")
        self._radio_type = RadioType.ezsp

        schema = {
            vol.Required(
                CONF_DEVICE_PATH, default=self._device_path or vol.UNDEFINED
            ): str
        }

        radio_schema = self._radio_type.controller.SCHEMA_DEVICE.schema
        assert not isinstance(radio_schema, vol.Schema)

        for param, value in radio_schema.items():
            if param in SUPPORTED_PORT_SETTINGS:
                schema[param] = value

        try:
            self._device_settings = vol.Schema(schema)(data.get("port"))
        except vol.Invalid:
            return self.async_abort(reason="invalid_hardware_data")

        self._title = data.get("name", data["port"]["path"])

        self._set_confirm_only()
        return await self.async_step_confirm_hardware()

    async def async_step_confirm_hardware(self, user_input=None):
        """Confirm a hardware discovery."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return await self._async_create_radio_entity()

        return self.async_show_form(
            step_id="confirm_hardware",
            description_placeholders={CONF_NAME: self._title},
        )
