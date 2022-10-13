"""Config flow for ZHA."""
from __future__ import annotations

import asyncio
import collections
import contextlib
import copy
import json
import logging
import os
from typing import Any

import serial.tools.list_ports
import voluptuous as vol
from zigpy.application import ControllerApplication
import zigpy.backups
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.exceptions import NetworkNotFormed

from homeassistant import config_entries
from homeassistant.components import onboarding, usb, zeroconf
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult
from homeassistant.helpers.selector import FileSelector, FileSelectorConfig
from homeassistant.util import dt

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
    EZSP_OVERWRITE_EUI64,
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
FORMATION_FORM_NEW_NETWORK = "form_new_network"
FORMATION_REUSE_SETTINGS = "reuse_settings"
FORMATION_CHOOSE_AUTOMATIC_BACKUP = "choose_automatic_backup"
FORMATION_UPLOAD_MANUAL_BACKUP = "upload_manual_backup"

CHOOSE_AUTOMATIC_BACKUP = "choose_automatic_backup"
OVERWRITE_COORDINATOR_IEEE = "overwrite_coordinator_ieee"

OPTIONS_INTENT_MIGRATE = "intent_migrate"
OPTIONS_INTENT_RECONFIGURE = "intent_reconfigure"

UPLOADED_BACKUP_FILE = "uploaded_backup_file"

DEFAULT_ZHA_ZEROCONF_PORT = 6638
ESPHOME_API_PORT = 6053

CONNECT_DELAY_S = 1.0

_LOGGER = logging.getLogger(__name__)


def _format_backup_choice(
    backup: zigpy.backups.NetworkBackup, *, pan_ids: bool = True
) -> str:
    """Format network backup info into a short piece of text."""
    if not pan_ids:
        return dt.as_local(backup.backup_time).strftime("%c")

    identifier = (
        # PAN ID
        f"{str(backup.network_info.pan_id)[2:]}"
        # EPID
        f":{str(backup.network_info.extended_pan_id).replace(':', '')}"
    ).lower()

    return f"{dt.as_local(backup.backup_time).strftime('%c')} ({identifier})"


def _allow_overwrite_ezsp_ieee(
    backup: zigpy.backups.NetworkBackup,
) -> zigpy.backups.NetworkBackup:
    """Return a new backup with the flag to allow overwriting the EZSP EUI64."""
    new_stack_specific = copy.deepcopy(backup.network_info.stack_specific)
    new_stack_specific.setdefault("ezsp", {})[EZSP_OVERWRITE_EUI64] = True

    return backup.replace(
        network_info=backup.network_info.replace(stack_specific=new_stack_specific)
    )


def _prevent_overwrite_ezsp_ieee(
    backup: zigpy.backups.NetworkBackup,
) -> zigpy.backups.NetworkBackup:
    """Return a new backup without the flag to allow overwriting the EZSP EUI64."""
    if "ezsp" not in backup.network_info.stack_specific:
        return backup

    new_stack_specific = copy.deepcopy(backup.network_info.stack_specific)
    new_stack_specific.setdefault("ezsp", {}).pop(EZSP_OVERWRITE_EUI64, None)

    return backup.replace(
        network_info=backup.network_info.replace(stack_specific=new_stack_specific)
    )


class BaseZhaFlow(FlowHandler):
    """Mixin for common ZHA flow steps and forms."""

    def __init__(self) -> None:
        """Initialize flow instance."""
        super().__init__()

        self._device_path: str | None = None
        self._device_settings: dict[str, Any] | None = None
        self._radio_type: RadioType | None = None
        self._title: str | None = None
        self._current_settings: zigpy.backups.NetworkBackup | None = None
        self._backups: list[zigpy.backups.NetworkBackup] = []
        self._chosen_backup: zigpy.backups.NetworkBackup | None = None

    @contextlib.asynccontextmanager
    async def _connect_zigpy_app(self) -> ControllerApplication:
        """Connect to the radio with the current config and then clean up."""
        assert self._radio_type is not None

        config = self.hass.data.get(DATA_ZHA, {}).get(DATA_ZHA_CONFIG, {})
        app_config = config.get(CONF_ZIGPY, {}).copy()

        database_path = config.get(
            CONF_DATABASE,
            self.hass.config.path(DEFAULT_DATABASE_NAME),
        )

        # Don't create `zigbee.db` if it doesn't already exist
        if not await self.hass.async_add_executor_job(os.path.exists, database_path):
            database_path = None

        app_config[CONF_DATABASE] = database_path
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
            await asyncio.sleep(CONNECT_DELAY_S)

    async def _restore_backup(
        self, backup: zigpy.backups.NetworkBackup, **kwargs: Any
    ) -> None:
        """Restore the provided network backup, passing through kwargs."""
        if self._current_settings is not None and self._current_settings.supersedes(
            self._chosen_backup
        ):
            return

        async with self._connect_zigpy_app() as app:
            await app.backups.restore_backup(backup, **kwargs)

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

    async def _async_create_radio_entity(self) -> FlowResult:
        """Create a config entity with the current flow state."""
        assert self._title is not None
        assert self._radio_type is not None
        assert self._device_path is not None
        assert self._device_settings is not None

        device_settings = self._device_settings.copy()
        device_settings[CONF_DEVICE_PATH] = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, self._device_path
        )

        return self.async_create_entry(
            title=self._title,
            data={
                CONF_DEVICE: device_settings,
                CONF_RADIO_TYPE: self._radio_type.name,
            },
        )

    async def async_step_choose_serial_port(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose a serial port."""
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

        # Pre-select the currently configured port
        default_port = vol.UNDEFINED

        if self._device_path is not None:
            for description, port in zip(list_of_ports, ports):
                if port.device == self._device_path:
                    default_port = description
                    break
            else:
                default_port = CONF_MANUAL_PATH

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_PATH, default=default_port): vol.In(
                    list_of_ports
                )
            }
        )
        return self.async_show_form(step_id="choose_serial_port", data_schema=schema)

    async def async_step_manual_pick_radio_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manually select the radio type."""
        if user_input is not None:
            self._radio_type = RadioType.get_by_description(user_input[CONF_RADIO_TYPE])
            return await self.async_step_manual_port_config()

        # Pre-select the current radio type
        default = vol.UNDEFINED

        if self._radio_type is not None:
            default = self._radio_type.description

        schema = {
            vol.Required(CONF_RADIO_TYPE, default=default): vol.In(RadioType.list())
        }

        return self.async_show_form(
            step_id="manual_pick_radio_type",
            data_schema=vol.Schema(schema),
        )

    async def async_step_manual_port_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter port settings specific for this type of radio."""
        assert self._radio_type is not None
        errors = {}

        if user_input is not None:
            self._title = user_input[CONF_DEVICE_PATH]
            self._device_path = user_input[CONF_DEVICE_PATH]
            self._device_settings = user_input.copy()

            if await self._radio_type.controller.probe(user_input):
                return await self.async_step_choose_formation_strategy()

            errors["base"] = "cannot_connect"

        schema = {
            vol.Required(
                CONF_DEVICE_PATH, default=self._device_path or vol.UNDEFINED
            ): str
        }

        source = self.context.get("source")
        for param, value in self._radio_type.controller.SCHEMA_DEVICE.schema.items():
            if param not in SUPPORTED_PORT_SETTINGS:
                continue

            if source == config_entries.SOURCE_ZEROCONF and param == CONF_BAUDRATE:
                value = 115200
                param = vol.Required(CONF_BAUDRATE, default=value)
            elif self._device_settings is not None and param in self._device_settings:
                param = vol.Required(str(param), default=self._device_settings[param])

            schema[param] = value

        return self.async_show_form(
            step_id="manual_port_config",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def _async_load_network_settings(self) -> None:
        """Connect to the radio and load its current network settings."""
        async with self._connect_zigpy_app() as app:
            # Check if the stick has any settings and load them
            try:
                await app.load_network_info()
            except NetworkNotFormed:
                pass
            else:
                self._current_settings = zigpy.backups.NetworkBackup(
                    network_info=app.state.network_info,
                    node_info=app.state.node_info,
                )

            # The list of backups will always exist
            self._backups = app.backups.backups.copy()

    async def async_step_choose_formation_strategy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose how to deal with the current radio's settings."""
        await self._async_load_network_settings()

        strategies = []

        # Check if we have any automatic backups *and* if the backups differ from
        # the current radio settings, if they exist (since restoring would be redundant)
        if self._backups and (
            self._current_settings is None
            or any(
                not backup.is_compatible_with(self._current_settings)
                for backup in self._backups
            )
        ):
            strategies.append(CHOOSE_AUTOMATIC_BACKUP)

        if self._current_settings is not None:
            strategies.append(FORMATION_REUSE_SETTINGS)

        strategies.append(FORMATION_UPLOAD_MANUAL_BACKUP)
        strategies.append(FORMATION_FORM_NEW_NETWORK)

        return self.async_show_menu(
            step_id="choose_formation_strategy",
            menu_options=strategies,
        )

    async def async_step_reuse_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reuse the existing network settings on the stick."""
        return await self._async_create_radio_entity()

    async def async_step_form_new_network(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Form a brand new network."""
        async with self._connect_zigpy_app() as app:
            await app.form_network()

        return await self._async_create_radio_entity()

    def _parse_uploaded_backup(
        self, uploaded_file_id: str
    ) -> zigpy.backups.NetworkBackup:
        """Read and parse an uploaded backup JSON file."""
        with process_uploaded_file(self.hass, uploaded_file_id) as file_path:
            contents = file_path.read_text()

        return zigpy.backups.NetworkBackup.from_dict(json.loads(contents))

    async def async_step_upload_manual_backup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Upload and restore a coordinator backup JSON file."""
        errors = {}

        if user_input is not None:
            try:
                self._chosen_backup = await self.hass.async_add_executor_job(
                    self._parse_uploaded_backup, user_input[UPLOADED_BACKUP_FILE]
                )
            except ValueError:
                errors["base"] = "invalid_backup_json"
            else:
                return await self.async_step_maybe_confirm_ezsp_restore()

        return self.async_show_form(
            step_id="upload_manual_backup",
            data_schema=vol.Schema(
                {
                    vol.Required(UPLOADED_BACKUP_FILE): FileSelector(
                        FileSelectorConfig(accept=".json,application/json")
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_choose_automatic_backup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose an automatic backup."""
        if self.show_advanced_options:
            # Always show the PAN IDs when in advanced mode
            choices = [
                _format_backup_choice(backup, pan_ids=True) for backup in self._backups
            ]
        else:
            # Only show the PAN IDs for multiple backups taken on the same day
            num_backups_on_date = collections.Counter(
                backup.backup_time.date() for backup in self._backups
            )
            choices = [
                _format_backup_choice(
                    backup, pan_ids=(num_backups_on_date[backup.backup_time.date()] > 1)
                )
                for backup in self._backups
            ]

        if user_input is not None:
            index = choices.index(user_input[CHOOSE_AUTOMATIC_BACKUP])
            self._chosen_backup = self._backups[index]

            return await self.async_step_maybe_confirm_ezsp_restore()

        return self.async_show_form(
            step_id="choose_automatic_backup",
            data_schema=vol.Schema(
                {
                    vol.Required(CHOOSE_AUTOMATIC_BACKUP, default=choices[0]): vol.In(
                        choices
                    ),
                }
            ),
        )

    async def async_step_maybe_confirm_ezsp_restore(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm restore for EZSP radios that require permanent IEEE writes."""
        assert self._chosen_backup is not None

        if self._radio_type != RadioType.ezsp:
            await self._restore_backup(self._chosen_backup)
            return await self._async_create_radio_entity()

        # We have no way to partially load network settings if no network is formed
        if self._current_settings is None:
            # Since we are going to be restoring the backup anyways, write it to the
            # radio without overwriting the IEEE but don't take a backup with these
            # temporary settings
            temp_backup = _prevent_overwrite_ezsp_ieee(self._chosen_backup)
            await self._restore_backup(temp_backup, create_new=False)
            await self._async_load_network_settings()

            assert self._current_settings is not None

        if (
            self._current_settings.node_info.ieee == self._chosen_backup.node_info.ieee
            or not self._current_settings.network_info.metadata["ezsp"][
                "can_write_custom_eui64"
            ]
        ):
            # No point in prompting the user if the backup doesn't have a new IEEE
            # address or if there is no way to overwrite the IEEE address a second time
            await self._restore_backup(self._chosen_backup)

            return await self._async_create_radio_entity()

        if user_input is not None:
            backup = self._chosen_backup

            if user_input[OVERWRITE_COORDINATOR_IEEE]:
                backup = _allow_overwrite_ezsp_ieee(backup)

            # If the user declined to overwrite the IEEE *and* we wrote the backup to
            # their empty radio above, restoring it again would be redundant.
            await self._restore_backup(backup)

            return await self._async_create_radio_entity()

        return self.async_show_form(
            step_id="maybe_confirm_ezsp_restore",
            data_schema=vol.Schema(
                {vol.Required(OVERWRITE_COORDINATOR_IEEE, default=True): bool}
            ),
        )


class ZhaConfigFlowHandler(BaseZhaFlow, config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return ZhaOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a zha config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_choose_serial_port(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a discovery."""
        self._set_confirm_only()

        # Don't permit discovery if ZHA is already set up
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Without confirmation, discovery can automatically progress into parts of the
        # config flow logic that interacts with hardware!
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            # Probe the radio type if we don't have one yet
            if self._radio_type is None and not await self._detect_radio_type():
                # This path probably will not happen now that we have
                # more precise USB matching unless there is a problem
                # with the device
                return self.async_abort(reason="usb_probe_failed")

            if self._device_settings is None:
                return await self.async_step_manual_port_config()

            return await self.async_step_choose_formation_strategy()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={CONF_NAME: self._title},
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
        self.context["title_placeholders"] = {CONF_NAME: self._title}
        return await self.async_step_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        # Hostname is format: livingroom.local.
        local_name = discovery_info.hostname[:-1]
        port = discovery_info.port or DEFAULT_ZHA_ZEROCONF_PORT

        # Fix incorrect port for older TubesZB devices
        if "tube" in local_name and port == ESPHOME_API_PORT:
            port = DEFAULT_ZHA_ZEROCONF_PORT

        if "radio_type" in discovery_info.properties:
            self._radio_type = RadioType[discovery_info.properties["radio_type"]]
        elif "efr32" in local_name:
            self._radio_type = RadioType.ezsp
        else:
            self._radio_type = RadioType.znp

        node_name = local_name[: -len(".local")]
        device_path = f"socket://{discovery_info.host}:{port}"

        if current_entry := await self.async_set_unique_id(node_name):
            self._abort_if_unique_id_configured(
                updates={
                    CONF_DEVICE: {
                        **current_entry.data.get(CONF_DEVICE, {}),
                        CONF_DEVICE_PATH: device_path,
                    },
                }
            )

        self.context["title_placeholders"] = {CONF_NAME: node_name}
        self._title = device_path
        self._device_path = device_path

        return await self.async_step_confirm()

    async def async_step_hardware(
        self, data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hardware flow."""
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
            device_settings = vol.Schema(schema)(data.get("port"))
        except vol.Invalid:
            return self.async_abort(reason="invalid_hardware_data")

        self._title = data.get("name", data["port"]["path"])
        self._device_path = device_settings[CONF_DEVICE_PATH]
        self._device_settings = device_settings

        return await self.async_step_confirm()


class ZhaOptionsFlowHandler(BaseZhaFlow, config_entries.OptionsFlow):
    """Handle an options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self.config_entry = config_entry

        self._device_path = config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH]
        self._device_settings = config_entry.data[CONF_DEVICE]
        self._radio_type = RadioType[config_entry.data[CONF_RADIO_TYPE]]
        self._title = config_entry.title

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Launch the options flow."""
        if user_input is not None:
            try:
                await self.hass.config_entries.async_unload(self.config_entry.entry_id)
            except config_entries.OperationNotAllowed:
                # ZHA is not running
                pass

            return await self.async_step_prompt_migrate_or_reconfigure()

        return self.async_show_form(step_id="init")

    async def async_step_prompt_migrate_or_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm if we are migrating adapters or just re-configuring."""

        return self.async_show_menu(
            step_id="prompt_migrate_or_reconfigure",
            menu_options=[
                OPTIONS_INTENT_RECONFIGURE,
                OPTIONS_INTENT_MIGRATE,
            ],
        )

    async def async_step_intent_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Virtual step for when the user is reconfiguring the integration."""
        return await self.async_step_choose_serial_port()

    async def async_step_intent_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the user wants to reset their current radio."""

        if user_input is not None:
            # Reset the current adapter
            async with self._connect_zigpy_app() as app:
                await app.reset_network_info()

            return await self.async_step_instruct_unplug()

        return self.async_show_form(step_id="intent_migrate")

    async def async_step_instruct_unplug(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Instruct the user to unplug the current radio, if possible."""

        if user_input is not None:
            # Now that the old radio is gone, we can scan for serial ports again
            return await self.async_step_choose_serial_port()

        return self.async_show_form(step_id="instruct_unplug")

    async def _async_create_radio_entity(self):
        """Re-implementation of the base flow's final step to update the config."""
        device_settings = self._device_settings.copy()
        device_settings[CONF_DEVICE_PATH] = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, self._device_path
        )

        # Avoid creating both `.options` and `.data` by directly writing `data` here
        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                CONF_DEVICE: device_settings,
                CONF_RADIO_TYPE: self._radio_type.name,
            },
            options=self.config_entry.options,
        )

        # Reload ZHA after we finish
        await self.hass.config_entries.async_setup(self.config_entry.entry_id)

        # Intentionally do not set `data` to avoid creating `options`, we set it above
        return self.async_create_entry(title=self._title, data={})

    def async_remove(self):
        """Maybe reload ZHA if the flow is aborted."""
        if self.config_entry.state not in (
            config_entries.ConfigEntryState.SETUP_ERROR,
            config_entries.ConfigEntryState.NOT_LOADED,
        ):
            return

        self.hass.async_create_task(
            self.hass.config_entries.async_setup(self.config_entry.entry_id)
        )
