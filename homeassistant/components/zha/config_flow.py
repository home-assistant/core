"""Config flow for ZHA."""

from __future__ import annotations

import collections
from contextlib import suppress
import json
from typing import Any

import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo
import voluptuous as vol
from zha.application.const import RadioType
import zigpy.backups
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant.components import onboarding, usb, zeroconf
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.components.homeassistant_yellow import hardware as yellow_hardware
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_ZEROCONF,
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OperationNotAllowed,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import FileSelector, FileSelectorConfig
from homeassistant.util import dt as dt_util

from .const import CONF_BAUDRATE, CONF_FLOW_CONTROL, CONF_RADIO_TYPE, DOMAIN
from .radio_manager import (
    DEVICE_SCHEMA,
    HARDWARE_DISCOVERY_SCHEMA,
    RECOMMENDED_RADIOS,
    ProbeResult,
    ZhaRadioManager,
)

CONF_MANUAL_PATH = "Enter Manually"
SUPPORTED_PORT_SETTINGS = (
    CONF_BAUDRATE,
    CONF_FLOW_CONTROL,
)
DECONZ_DOMAIN = "deconz"

FORMATION_STRATEGY = "formation_strategy"
FORMATION_FORM_NEW_NETWORK = "form_new_network"
FORMATION_FORM_INITIAL_NETWORK = "form_initial_network"
FORMATION_REUSE_SETTINGS = "reuse_settings"
FORMATION_CHOOSE_AUTOMATIC_BACKUP = "choose_automatic_backup"
FORMATION_UPLOAD_MANUAL_BACKUP = "upload_manual_backup"

CHOOSE_AUTOMATIC_BACKUP = "choose_automatic_backup"
OVERWRITE_COORDINATOR_IEEE = "overwrite_coordinator_ieee"

OPTIONS_INTENT_MIGRATE = "intent_migrate"
OPTIONS_INTENT_RECONFIGURE = "intent_reconfigure"

UPLOADED_BACKUP_FILE = "uploaded_backup_file"

REPAIR_MY_URL = "https://my.home-assistant.io/redirect/repairs/"

DEFAULT_ZHA_ZEROCONF_PORT = 6638
ESPHOME_API_PORT = 6053


def _format_backup_choice(
    backup: zigpy.backups.NetworkBackup, *, pan_ids: bool = True
) -> str:
    """Format network backup info into a short piece of text."""
    if not pan_ids:
        return dt_util.as_local(backup.backup_time).strftime("%c")

    identifier = (
        # PAN ID
        f"{str(backup.network_info.pan_id)[2:]}"
        # EPID
        f":{str(backup.network_info.extended_pan_id).replace(':', '')}"
    ).lower()

    return f"{dt_util.as_local(backup.backup_time).strftime('%c')} ({identifier})"


async def list_serial_ports(hass: HomeAssistant) -> list[ListPortInfo]:
    """List all serial ports, including the Yellow radio and the multi-PAN addon."""
    ports = await hass.async_add_executor_job(serial.tools.list_ports.comports)

    # Add useful info to the Yellow's serial port selection screen
    try:
        yellow_hardware.async_info(hass)
    except HomeAssistantError:
        pass
    else:
        yellow_radio = next(p for p in ports if p.device == "/dev/ttyAMA1")
        yellow_radio.description = "Yellow Zigbee module"
        yellow_radio.manufacturer = "Nabu Casa"

    # Present the multi-PAN addon as a setup option, if it's available
    multipan_manager = await silabs_multiprotocol_addon.get_multiprotocol_addon_manager(
        hass
    )

    try:
        addon_info = await multipan_manager.async_get_addon_info()
    except (AddonError, KeyError):
        addon_info = None

    if addon_info is not None and addon_info.state != AddonState.NOT_INSTALLED:
        addon_port = ListPortInfo(
            device=silabs_multiprotocol_addon.get_zigbee_socket(),
            skip_link_detection=True,
        )

        addon_port.description = "Multiprotocol add-on"
        addon_port.manufacturer = "Nabu Casa"
        ports.append(addon_port)

    return ports


class BaseZhaFlow(ConfigEntryBaseFlow):
    """Mixin for common ZHA flow steps and forms."""

    _hass: HomeAssistant
    _title: str

    def __init__(self) -> None:
        """Initialize flow instance."""
        super().__init__()

        self._hass = None  # type: ignore[assignment]
        self._radio_mgr = ZhaRadioManager()

    @property
    def hass(self) -> HomeAssistant:
        """Return hass."""
        return self._hass

    @hass.setter
    def hass(self, hass: HomeAssistant) -> None:
        """Set hass."""
        self._hass = hass
        self._radio_mgr.hass = hass

    async def _async_create_radio_entry(self) -> ConfigFlowResult:
        """Create a config entry with the current flow state."""
        assert self._radio_mgr.radio_type is not None
        assert self._radio_mgr.device_path is not None
        assert self._radio_mgr.device_settings is not None

        device_settings = self._radio_mgr.device_settings.copy()
        device_settings[CONF_DEVICE_PATH] = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, self._radio_mgr.device_path
        )

        return self.async_create_entry(
            title=self._title,
            data={
                CONF_DEVICE: DEVICE_SCHEMA(device_settings),
                CONF_RADIO_TYPE: self._radio_mgr.radio_type.name,
            },
        )

    async def async_step_choose_serial_port(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a serial port."""
        ports = await list_serial_ports(self.hass)
        list_of_ports = [
            f"{p}{', s/n: ' + p.serial_number if p.serial_number else ''}"
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
            self._radio_mgr.device_path = port.device

            probe_result = await self._radio_mgr.detect_radio_type()
            if probe_result == ProbeResult.WRONG_FIRMWARE_INSTALLED:
                return self.async_abort(
                    reason="wrong_firmware_installed",
                    description_placeholders={"repair_url": REPAIR_MY_URL},
                )
            if probe_result == ProbeResult.PROBING_FAILED:
                # Did not autodetect anything, proceed to manual selection
                return await self.async_step_manual_pick_radio_type()

            self._title = (
                f"{port.description}{', s/n: ' + port.serial_number if port.serial_number else ''}"
                f" - {port.manufacturer}"
                if port.manufacturer
                else ""
            )

            return await self.async_step_verify_radio()

        # Pre-select the currently configured port
        default_port: vol.Undefined | str = vol.UNDEFINED

        if self._radio_mgr.device_path is not None:
            for description, port in zip(list_of_ports, ports, strict=False):
                if port.device == self._radio_mgr.device_path:
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
    ) -> ConfigFlowResult:
        """Manually select the radio type."""
        if user_input is not None:
            self._radio_mgr.radio_type = RadioType.get_by_description(
                user_input[CONF_RADIO_TYPE]
            )
            return await self.async_step_manual_port_config()

        # Pre-select the current radio type
        default: vol.Undefined | str = vol.UNDEFINED

        if self._radio_mgr.radio_type is not None:
            default = self._radio_mgr.radio_type.description

        schema = {
            vol.Required(CONF_RADIO_TYPE, default=default): vol.In(RadioType.list())
        }

        return self.async_show_form(
            step_id="manual_pick_radio_type",
            data_schema=vol.Schema(schema),
        )

    async def async_step_manual_port_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter port settings specific for this type of radio."""
        assert self._radio_mgr.radio_type is not None
        errors = {}

        if user_input is not None:
            self._title = user_input[CONF_DEVICE_PATH]
            self._radio_mgr.device_path = user_input[CONF_DEVICE_PATH]
            self._radio_mgr.device_settings = user_input.copy()

            if await self._radio_mgr.radio_type.controller.probe(user_input):
                return await self.async_step_verify_radio()

            errors["base"] = "cannot_connect"

        schema = {
            vol.Required(
                CONF_DEVICE_PATH, default=self._radio_mgr.device_path or vol.UNDEFINED
            ): str
        }

        source = self.context.get("source")
        for (
            param,
            value,
        ) in DEVICE_SCHEMA.schema.items():
            if param not in SUPPORTED_PORT_SETTINGS:
                continue

            if source == SOURCE_ZEROCONF and param == CONF_BAUDRATE:
                value = 115200
                param = vol.Required(CONF_BAUDRATE, default=value)
            elif (
                self._radio_mgr.device_settings is not None
                and param in self._radio_mgr.device_settings
            ):
                param = vol.Required(
                    str(param), default=self._radio_mgr.device_settings[param]
                )

            schema[param] = value

        return self.async_show_form(
            step_id="manual_port_config",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_verify_radio(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a warning step to dissuade the use of deprecated radios."""
        assert self._radio_mgr.radio_type is not None

        # Skip this step if we are using a recommended radio
        if user_input is not None or self._radio_mgr.radio_type in RECOMMENDED_RADIOS:
            return await self.async_step_choose_formation_strategy()

        return self.async_show_form(
            step_id="verify_radio",
            description_placeholders={
                CONF_NAME: self._radio_mgr.radio_type.description,
                "docs_recommended_adapters_url": (
                    "https://www.home-assistant.io/integrations/zha/#recommended-zigbee-radio-adapters-and-modules"
                ),
            },
        )

    async def async_step_choose_formation_strategy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to deal with the current radio's settings."""
        await self._radio_mgr.async_load_network_settings()

        strategies = []

        # Check if we have any automatic backups *and* if the backups differ from
        # the current radio settings, if they exist (since restoring would be redundant)
        if self._radio_mgr.backups and (
            self._radio_mgr.current_settings is None
            or any(
                not backup.is_compatible_with(self._radio_mgr.current_settings)
                for backup in self._radio_mgr.backups
            )
        ):
            strategies.append(CHOOSE_AUTOMATIC_BACKUP)

        if self._radio_mgr.current_settings is not None:
            strategies.append(FORMATION_REUSE_SETTINGS)

        strategies.append(FORMATION_UPLOAD_MANUAL_BACKUP)

        # Do not show "erase network settings" if there are none to erase
        if self._radio_mgr.current_settings is None:
            strategies.append(FORMATION_FORM_INITIAL_NETWORK)
        else:
            strategies.append(FORMATION_FORM_NEW_NETWORK)

        # Automatically form a new network if we're onboarding with a brand new radio
        if not onboarding.async_is_onboarded(self.hass) and set(strategies) == {
            FORMATION_UPLOAD_MANUAL_BACKUP,
            FORMATION_FORM_INITIAL_NETWORK,
        }:
            return await self.async_step_form_initial_network()

        # Otherwise, let the user choose
        return self.async_show_menu(
            step_id="choose_formation_strategy",
            menu_options=strategies,
        )

    async def async_step_reuse_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reuse the existing network settings on the stick."""
        return await self._async_create_radio_entry()

    async def async_step_form_initial_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form an initial network."""
        # This step exists only for translations, it does nothing new
        return await self.async_step_form_new_network(user_input)

    async def async_step_form_new_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form a brand-new network."""
        await self._radio_mgr.async_form_network()
        return await self._async_create_radio_entry()

    def _parse_uploaded_backup(
        self, uploaded_file_id: str
    ) -> zigpy.backups.NetworkBackup:
        """Read and parse an uploaded backup JSON file."""
        with process_uploaded_file(self.hass, uploaded_file_id) as file_path:
            contents = file_path.read_text()

        return zigpy.backups.NetworkBackup.from_dict(json.loads(contents))

    async def async_step_upload_manual_backup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Upload and restore a coordinator backup JSON file."""
        errors = {}

        if user_input is not None:
            try:
                self._radio_mgr.chosen_backup = await self.hass.async_add_executor_job(
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
    ) -> ConfigFlowResult:
        """Choose an automatic backup."""
        if self.show_advanced_options:
            # Always show the PAN IDs when in advanced mode
            choices = [
                _format_backup_choice(backup, pan_ids=True)
                for backup in self._radio_mgr.backups
            ]
        else:
            # Only show the PAN IDs for multiple backups taken on the same day
            num_backups_on_date = collections.Counter(
                backup.backup_time.date() for backup in self._radio_mgr.backups
            )
            choices = [
                _format_backup_choice(
                    backup, pan_ids=(num_backups_on_date[backup.backup_time.date()] > 1)
                )
                for backup in self._radio_mgr.backups
            ]

        if user_input is not None:
            index = choices.index(user_input[CHOOSE_AUTOMATIC_BACKUP])
            self._radio_mgr.chosen_backup = self._radio_mgr.backups[index]

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
    ) -> ConfigFlowResult:
        """Confirm restore for EZSP radios that require permanent IEEE writes."""
        call_step_2 = await self._radio_mgr.async_restore_backup_step_1()
        if not call_step_2:
            return await self._async_create_radio_entry()

        if user_input is not None:
            await self._radio_mgr.async_restore_backup_step_2(
                user_input[OVERWRITE_COORDINATOR_IEEE]
            )
            return await self._async_create_radio_entry()

        return self.async_show_form(
            step_id="maybe_confirm_ezsp_restore",
            data_schema=vol.Schema(
                {vol.Required(OVERWRITE_COORDINATOR_IEEE, default=True): bool}
            ),
        )


class ZhaConfigFlowHandler(BaseZhaFlow, ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 4

    async def _set_unique_id_and_update_ignored_flow(
        self, unique_id: str, device_path: str
    ) -> None:
        """Set the flow's unique ID and update the device path in an ignored flow."""
        current_entry = await self.async_set_unique_id(unique_id)

        if not current_entry:
            return

        if current_entry.source != SOURCE_IGNORE:
            self._abort_if_unique_id_configured()
        else:
            # Only update the current entry if it is an ignored discovery
            self._abort_if_unique_id_configured(
                updates={
                    CONF_DEVICE: {
                        **current_entry.data.get(CONF_DEVICE, {}),
                        CONF_DEVICE_PATH: device_path,
                    },
                }
            )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return ZhaOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a ZHA config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_choose_serial_port(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovery."""
        self._set_confirm_only()

        # Don't permit discovery if ZHA is already set up
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Without confirmation, discovery can automatically progress into parts of the
        # config flow logic that interacts with hardware.
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            # Probe the radio type if we don't have one yet
            if self._radio_mgr.radio_type is None:
                probe_result = await self._radio_mgr.detect_radio_type()
            else:
                probe_result = ProbeResult.RADIO_TYPE_DETECTED

            if probe_result == ProbeResult.WRONG_FIRMWARE_INSTALLED:
                return self.async_abort(
                    reason="wrong_firmware_installed",
                    description_placeholders={"repair_url": REPAIR_MY_URL},
                )
            if probe_result == ProbeResult.PROBING_FAILED:
                # This path probably will not happen now that we have
                # more precise USB matching unless there is a problem
                # with the device
                return self.async_abort(reason="usb_probe_failed")

            if self._radio_mgr.device_settings is None:
                return await self.async_step_manual_port_config()

            return await self.async_step_verify_radio()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={CONF_NAME: self._title},
        )

    async def async_step_usb(
        self, discovery_info: usb.UsbServiceInfo
    ) -> ConfigFlowResult:
        """Handle usb discovery."""
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        dev_path = discovery_info.device

        await self._set_unique_id_and_update_ignored_flow(
            unique_id=f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}",
            device_path=dev_path,
        )

        # If they already have a discovery for deconz we ignore the usb discovery as
        # they probably want to use it there instead
        if self.hass.config_entries.flow.async_progress_by_handler(DECONZ_DOMAIN):
            return self.async_abort(reason="not_zha_device")
        for entry in self.hass.config_entries.async_entries(DECONZ_DOMAIN):
            if entry.source != SOURCE_IGNORE:
                return self.async_abort(reason="not_zha_device")

        self._radio_mgr.device_path = dev_path
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
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # Hostname is format: livingroom.local.
        local_name = discovery_info.hostname[:-1]
        port = discovery_info.port or DEFAULT_ZHA_ZEROCONF_PORT

        # Fix incorrect port for older TubesZB devices
        if "tube" in local_name and port == ESPHOME_API_PORT:
            port = DEFAULT_ZHA_ZEROCONF_PORT

        if "radio_type" in discovery_info.properties:
            self._radio_mgr.radio_type = self._radio_mgr.parse_radio_type(
                discovery_info.properties["radio_type"]
            )
        elif "efr32" in local_name:
            self._radio_mgr.radio_type = RadioType.ezsp
        else:
            self._radio_mgr.radio_type = RadioType.znp

        node_name = local_name.removesuffix(".local")
        device_path = f"socket://{discovery_info.host}:{port}"

        await self._set_unique_id_and_update_ignored_flow(
            unique_id=node_name,
            device_path=device_path,
        )

        self.context["title_placeholders"] = {CONF_NAME: node_name}
        self._title = device_path
        self._radio_mgr.device_path = device_path

        return await self.async_step_confirm()

    async def async_step_hardware(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle hardware flow."""
        try:
            discovery_data = HARDWARE_DISCOVERY_SCHEMA(data)
        except vol.Invalid:
            return self.async_abort(reason="invalid_hardware_data")

        name = discovery_data["name"]
        radio_type = self._radio_mgr.parse_radio_type(discovery_data["radio_type"])
        device_settings = discovery_data["port"]
        device_path = device_settings[CONF_DEVICE_PATH]

        await self._set_unique_id_and_update_ignored_flow(
            unique_id=f"{name}_{radio_type.name}_{device_path}",
            device_path=device_path,
        )

        self._title = name
        self._radio_mgr.radio_type = radio_type
        self._radio_mgr.device_path = device_path
        self._radio_mgr.device_settings = device_settings
        self.context["title_placeholders"] = {CONF_NAME: name}

        return await self.async_step_confirm()


class ZhaOptionsFlowHandler(BaseZhaFlow, OptionsFlow):
    """Handle an options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self.config_entry = config_entry

        self._radio_mgr.device_path = config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH]
        self._radio_mgr.device_settings = config_entry.data[CONF_DEVICE]
        self._radio_mgr.radio_type = RadioType[config_entry.data[CONF_RADIO_TYPE]]
        self._title = config_entry.title

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Launch the options flow."""
        if user_input is not None:
            # OperationNotAllowed: ZHA is not running
            with suppress(OperationNotAllowed):
                await self.hass.config_entries.async_unload(self.config_entry.entry_id)

            return await self.async_step_prompt_migrate_or_reconfigure()

        return self.async_show_form(step_id="init")

    async def async_step_prompt_migrate_or_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Virtual step for when the user is reconfiguring the integration."""
        return await self.async_step_choose_serial_port()

    async def async_step_intent_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the user wants to reset their current radio."""

        if user_input is not None:
            await self._radio_mgr.async_reset_adapter()

            return await self.async_step_instruct_unplug()

        return self.async_show_form(step_id="intent_migrate")

    async def async_step_instruct_unplug(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Instruct the user to unplug the current radio, if possible."""

        if user_input is not None:
            # Now that the old radio is gone, we can scan for serial ports again
            return await self.async_step_choose_serial_port()

        return self.async_show_form(step_id="instruct_unplug")

    async def _async_create_radio_entry(self):
        """Re-implementation of the base flow's final step to update the config."""
        device_settings = self._radio_mgr.device_settings.copy()
        device_settings[CONF_DEVICE_PATH] = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, self._radio_mgr.device_path
        )

        # Avoid creating both `.options` and `.data` by directly writing `data` here
        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                CONF_DEVICE: device_settings,
                CONF_RADIO_TYPE: self._radio_mgr.radio_type.name,
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
            ConfigEntryState.SETUP_ERROR,
            ConfigEntryState.NOT_LOADED,
        ):
            return

        self.hass.async_create_task(
            self.hass.config_entries.async_setup(self.config_entry.entry_id)
        )
