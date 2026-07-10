"""Config flow for Z-Wave JS integration."""

import asyncio
import base64
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, override

from awesomeversion import AwesomeVersion
from propcache.api import cached_property
import voluptuous as vol
from zwave_js_server.client import Client
from zwave_js_server.exceptions import FailedCommand
from zwave_js_server.model.driver import Driver
from zwave_js_server.version import VersionInfo

from homeassistant.components import usb
from homeassistant.components.hassio import AddonError, AddonInfo, AddonState
from homeassistant.config_entries import (
    SOURCE_ESPHOME,
    SOURCE_IGNORE,
    SOURCE_USB,
    SOURCE_ZEROCONF,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.service_info.esphome import ESPHomeServiceInfo
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .addon import get_addon_manager
from .const import (
    ADDON_SLUG,
    CONF_ADDON_DEVICE,
    CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_LR_S2_AUTHENTICATED_KEY,
    CONF_ADDON_NETWORK_KEY,
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
    CONF_ADDON_SOCKET,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_KEEP_OLD_DEVICES,
    CONF_LR_S2_ACCESS_CONTROL_KEY,
    CONF_LR_S2_AUTHENTICATED_KEY,
    CONF_S0_LEGACY_KEY,
    CONF_S2_ACCESS_CONTROL_KEY,
    CONF_S2_AUTHENTICATED_KEY,
    CONF_S2_UNAUTHENTICATED_KEY,
    CONF_SOCKET_PATH,
    CONF_USB_PATH,
    CONF_USE_ADDON,
    DOMAIN,
)
from .helpers import (
    CannotConnect,
    async_get_version_info,
    async_wait_for_driver_ready_event,
    format_home_id_for_display,
)
from .models import ZwaveJSConfigEntry

_LOGGER = logging.getLogger(__name__)

DEFAULT_URL = "ws://localhost:3000"
TITLE = "Z-Wave JS"

ADDON_SETUP_TIMEOUT = 5
ADDON_SETUP_TIMEOUT_ROUNDS = 40

CONF_ADDON_RF_REGION = "rf_region"

# Security key fields as (field name, add-on config key, config entry key).
KEY_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("s0_legacy", CONF_ADDON_S0_LEGACY_KEY, CONF_S0_LEGACY_KEY),
    ("s2_access_control", CONF_ADDON_S2_ACCESS_CONTROL_KEY, CONF_S2_ACCESS_CONTROL_KEY),
    ("s2_authenticated", CONF_ADDON_S2_AUTHENTICATED_KEY, CONF_S2_AUTHENTICATED_KEY),
    (
        "s2_unauthenticated",
        CONF_ADDON_S2_UNAUTHENTICATED_KEY,
        CONF_S2_UNAUTHENTICATED_KEY,
    ),
    (
        "lr_s2_access_control",
        CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY,
        CONF_LR_S2_ACCESS_CONTROL_KEY,
    ),
    (
        "lr_s2_authenticated",
        CONF_ADDON_LR_S2_AUTHENTICATED_KEY,
        CONF_LR_S2_AUTHENTICATED_KEY,
    ),
)


ADDON_USER_INPUT_MAP = {
    CONF_ADDON_DEVICE: CONF_USB_PATH,
    CONF_ADDON_SOCKET: CONF_SOCKET_PATH,
    **{addon_key: entry_key for _, addon_key, entry_key in KEY_FIELDS},
}


def migrate_network_key(addon_config: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate the legacy network key to the S0 legacy key.

    The network key was renamed to the S0 legacy key when S2 was added.
    Old add-on configs may still only carry the legacy network key.
    """
    migrated = dict(addon_config)
    if (network_key := migrated.pop(CONF_ADDON_NETWORK_KEY, None)) and not migrated.get(
        CONF_ADDON_S0_LEGACY_KEY
    ):
        migrated[CONF_ADDON_S0_LEGACY_KEY] = network_key
    return migrated


@dataclass
class SecurityKeys:
    """Security keys of a Z-Wave network."""

    s0_legacy: str | None = None
    s2_access_control: str | None = None
    s2_authenticated: str | None = None
    s2_unauthenticated: str | None = None
    lr_s2_access_control: str | None = None
    lr_s2_authenticated: str | None = None

    @classmethod
    def from_addon_config(
        cls, addon_config: Mapping[str, Any], defaults: SecurityKeys | None = None
    ) -> SecurityKeys:
        """Return keys from an add-on config, falling back to defaults."""
        # Read a legacy network key as the S0 legacy key.
        addon_config = migrate_network_key(addon_config)
        return cls(
            **{
                field: addon_config.get(
                    addon_key,
                    ((getattr(defaults, field) if defaults else None) or ""),
                )
                for field, addon_key, _ in KEY_FIELDS
            }
        )

    def updated_from_user_input(self, user_input: Mapping[str, Any]) -> SecurityKeys:
        """Return keys updated from user input, with these keys as defaults."""
        return SecurityKeys(
            **{
                field: user_input.get(entry_key, getattr(self, field) or "")
                for field, _, entry_key in KEY_FIELDS
            }
        )

    def to_addon_config(self) -> dict[str, str | None]:
        """Return the keys as add-on config options."""
        return {addon_key: getattr(self, field) for field, addon_key, _ in KEY_FIELDS}

    def to_entry_data(self) -> dict[str, str | None]:
        """Return the keys as config entry data."""
        return {entry_key: getattr(self, field) for field, _, entry_key in KEY_FIELDS}


ON_SUPERVISOR_SCHEMA = vol.Schema({vol.Optional(CONF_USE_ADDON, default=True): bool})
MIN_MIGRATION_SDK_VERSION = AwesomeVersion("6.61")

# Steps at which another flow has not yet changed any shared state,
# e.g. the add-on config, and can be aborted safely when a config entry
# is created by a different flow. Steps that can be part of a migration,
# e.g. choose_serial_port, must not be in this set.
ABORT_SAFE_STEPS = {
    "configure_addon_user",
    "configure_security_keys",
    "confirm_migration",
    "hassio_confirm",
    "installation_type",
    "network_type",
    "on_supervisor",
    "zeroconf_confirm",
}

NETWORK_TYPE_NEW = "new"
NETWORK_TYPE_EXISTING = "existing"
ZWAVE_JS_SERVER_INSTRUCTIONS = (
    "https://www.home-assistant.io/integrations/zwave_js/"
    "#advanced-installation-instructions"
)
ZWAVE_JS_UI_MIGRATION_INSTRUCTIONS = (
    "https://www.home-assistant.io/integrations/zwave_js/"
    "#how-to-migrate-from-one-adapter-to-a-new-adapter-using-z-wave-js-ui"
)

RF_REGIONS = [
    "Australia/New Zealand",
    "China",
    "Europe",
    "Hong Kong",
    "India",
    "Israel",
    "Japan",
    "Korea",
    "Russia",
    "USA",
]

# USB devices to ignore in serial port selection (non-Z-Wave devices)
# Format: (manufacturer, description)
IGNORED_USB_DEVICES = {
    ("Nabu Casa", "SkyConnect v1.0"),
    ("Nabu Casa", "Home Assistant Connect ZBT-1"),
    ("Nabu Casa", "ZBT-2"),
}


def get_manual_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the manual step."""
    default_url = user_input.get(CONF_URL, DEFAULT_URL)
    return vol.Schema({vol.Required(CONF_URL, default=default_url): str})


def get_on_supervisor_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the on Supervisor step."""
    default_use_addon = user_input[CONF_USE_ADDON]
    return vol.Schema({vol.Required(CONF_USE_ADDON, default=default_use_addon): bool})


async def validate_input(hass: HomeAssistant, user_input: dict) -> VersionInfo:
    """Validate if the user input allows us to connect."""
    ws_address = user_input[CONF_URL]

    if not ws_address.startswith(("ws://", "wss://")):
        raise InvalidInput("invalid_ws_url")

    try:
        return await async_get_version_info(hass, ws_address)
    except CannotConnect as err:
        raise InvalidInput("cannot_connect") from err


async def async_get_usb_ports(hass: HomeAssistant) -> dict[str, str]:
    """Return a dict of USB ports and their friendly names."""
    port_descriptions = {}
    for port in await usb.async_scan_serial_ports(hass):
        if (port.manufacturer, port.description) in IGNORED_USB_DEVICES:
            continue

        human_name = usb.human_readable_device_name(
            port.device,
            port.serial_number,
            port.manufacturer,
            port.description,
            port.vid if isinstance(port, usb.USBDevice) else None,
            port.pid if isinstance(port, usb.USBDevice) else None,
        )
        port_descriptions[port.device] = human_name

    # Filter out "n/a" descriptions only if there are other ports available
    non_na_ports = {
        path: desc
        for path, desc in port_descriptions.items()
        if not desc.lower().startswith("n/a")
    }

    # If we have non-"n/a" ports, return only those; otherwise return all ports as-is
    return non_na_ports or port_descriptions


class AddonFlowManager:
    """Manage the Z-Wave JS add-on for the config flow.

    Wraps the add-on manager with flow-friendly error handling
    and tracks the original add-on config for reverts.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the add-on flow manager."""
        self.hass = hass
        self.addon_manager = get_addon_manager(hass)
        # Set to True if the add-on was running when its config was changed,
        # meaning a restart instead of a start is needed.
        self.restart_addon = False
        # Set to True once this flow has started a stopped add-on.
        self.addon_started = False
        # The add-on config before this flow changed it, for reverts.
        self.original_config: dict[str, Any] | None = None

    async def async_get_addon_info(self) -> AddonInfo:
        """Return Z-Wave JS add-on info."""
        try:
            addon_info: AddonInfo = await self.addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_info_failed") from err

        return addon_info

    async def async_set_addon_config(self, config_updates: dict) -> None:
        """Set Z-Wave JS add-on config."""
        addon_info = await self.async_get_addon_info()
        addon_config = addon_info.options

        new_addon_config = addon_config | config_updates

        if new_addon_config.get(CONF_ADDON_DEVICE) is None:
            new_addon_config.pop(CONF_ADDON_DEVICE, None)
        if new_addon_config.get(CONF_ADDON_SOCKET) is None:
            new_addon_config.pop(CONF_ADDON_SOCKET, None)

        if new_addon_config == addon_config:
            return

        if addon_info.state is AddonState.RUNNING:
            self.restart_addon = True
        if self.original_config is None:
            # Only capture the config before the first change,
            # so a revert restores the config from before the flow,
            # also if the flow changes the config multiple times,
            # e.g. when the RF region step sets the region.
            # Copy the add-on config to keep the objects separate.
            self.original_config = dict(addon_config)
        # Migrate a legacy network key to the S0 legacy key, then drop it.
        new_addon_config = migrate_network_key(new_addon_config)
        try:
            await self.addon_manager.async_set_addon_options(new_addon_config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_set_config_failed") from err

    async def async_install_addon(self) -> None:
        """Install the Z-Wave JS add-on."""
        await self.addon_manager.async_schedule_install_addon()

    async def async_stop_addon(self) -> None:
        """Stop the Z-Wave JS add-on."""
        await self.addon_manager.async_stop_addon()

    async def async_start_addon_and_wait(
        self, ws_address: str | None
    ) -> tuple[str, VersionInfo]:
        """(Re)start the add-on and wait until the server is reachable.

        Return the server websocket address and version info.
        """
        if self.restart_addon:
            await self.addon_manager.async_schedule_restart_addon()
        else:
            self.addon_started = True
            await self.addon_manager.async_schedule_start_addon()
        version_info: VersionInfo | None = None
        # Sleep some seconds to let the add-on start properly before connecting.
        for _ in range(ADDON_SETUP_TIMEOUT_ROUNDS):
            await asyncio.sleep(ADDON_SETUP_TIMEOUT)
            try:
                if not ws_address:
                    discovery_info = await self.async_get_addon_discovery_info()
                    ws_address = (
                        f"ws://{discovery_info['host']}:{discovery_info['port']}"
                    )
                version_info = await async_get_version_info(self.hass, ws_address)
            except (AbortFlow, CannotConnect) as err:
                _LOGGER.debug(
                    "Add-on not ready yet, waiting %s seconds: %s",
                    ADDON_SETUP_TIMEOUT,
                    err,
                )
            else:
                break
        else:
            raise CannotConnect("Failed to start Z-Wave JS add-on: timeout")

        assert version_info is not None
        return ws_address, version_info

    async def async_get_addon_discovery_info(self) -> dict:
        """Return add-on discovery info."""
        try:
            discovery_info_config = (
                await self.addon_manager.async_get_addon_discovery_info()
            )
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_get_discovery_info_failed") from err

        return discovery_info_config


class NvmMigrationManager:
    """Handle the NVM backup and restore of an adapter migration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the NVM migration manager."""
        self.hass = hass
        self.backup_data: bytes | None = None
        self.backup_filepath: Path | None = None

    async def async_backup(
        self, driver: Driver, update_progress: Callable[[float], None]
    ) -> None:
        """Back up the NVM of the current adapter and save it to a file."""

        @callback
        def forward_progress(event: dict) -> None:
            """Forward progress events to frontend."""
            update_progress(event["bytesRead"] / event["total"])

        controller = driver.controller
        unsub = controller.on("nvm backup progress", forward_progress)
        try:
            self.backup_data = await controller.async_backup_nvm_raw()
        except FailedCommand as err:
            raise AbortFlow(f"Failed to backup network: {err}") from err
        finally:
            unsub()

        # save the backup to a file just in case
        self.backup_filepath = Path(
            self.hass.config.path(
                f"zwavejs_nvm_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.bin"  # pylint: disable=home-assistant-enforce-naive-now
            )
        )
        try:
            await self.hass.async_add_executor_job(
                self.backup_filepath.write_bytes,
                self.backup_data,
            )
        except OSError as err:
            raise AbortFlow(f"Failed to save backup file: {err}") from err

    async def async_restore(
        self,
        config_entry: ZwaveJSConfigEntry,
        get_driver: Callable[[], Driver],
        update_progress: Callable[[float], None],
    ) -> None:
        """Restore the backup to the new adapter."""
        assert self.backup_data is not None

        # Make sure we keep the old devices
        # so that user customizations are not lost,
        # when loading the config entry.
        self.hass.config_entries.async_update_entry(
            config_entry, data=config_entry.data | {CONF_KEEP_OLD_DEVICES: True}
        )

        # Reload the config entry to reconnect the client after the addon restart
        await self.hass.config_entries.async_reload(config_entry.entry_id)

        data = config_entry.data.copy()
        data.pop(CONF_KEEP_OLD_DEVICES, None)
        self.hass.config_entries.async_update_entry(config_entry, data=data)

        @callback
        def forward_progress(event: dict) -> None:
            """Forward progress events to frontend."""
            if event["event"] == "nvm convert progress":
                # assume convert is 50% of the total progress
                update_progress(event["bytesRead"] / event["total"] * 0.5)
            elif event["event"] == "nvm restore progress":
                # assume restore is the rest of the progress
                update_progress(event["bytesWritten"] / event["total"] * 0.5 + 0.5)

        driver = get_driver()
        controller = driver.controller
        unsubs = [
            controller.on("nvm convert progress", forward_progress),
            controller.on("nvm restore progress", forward_progress),
        ]

        wait_for_driver_ready = async_wait_for_driver_ready_event(config_entry, driver)

        try:
            await controller.async_restore_nvm(
                self.backup_data, {"preserveRoutes": False}
            )
        except FailedCommand as err:
            raise AbortFlow(f"Failed to restore network: {err}") from err
        else:
            with suppress(TimeoutError):
                await wait_for_driver_ready()
            try:
                version_info = await async_get_version_info(
                    self.hass, config_entry.data[CONF_URL]
                )
            except CannotConnect:
                # Just log this error, as there's nothing to do about it here.
                # The stale unique id needs to be handled by a repair flow,
                # after the config entry has been reloaded.
                _LOGGER.error(
                    "Failed to get server version, cannot update config entry "
                    "unique id with new home id, after controller reset"
                )
            else:
                # The reload triggered by the driver ready event runs before
                # the unique id is updated here and hits the unknown adapter
                # branch on setup, which sets the keep old devices flag again.
                # Clear the flag so the reload below cleans up stale devices.
                data = {
                    key: value
                    for key, value in config_entry.data.items()
                    if key != CONF_KEEP_OLD_DEVICES
                }
                self.hass.config_entries.async_update_entry(
                    config_entry, data=data, unique_id=str(version_info.home_id)
                )

            # The config entry will also be reloaded when the driver is ready,
            # by the listener in the package module,
            # and two reloads are needed to clean up the stale controller device entry.
            # Since both the old and the new controller have the same node id,
            # but different hardware identifiers, the integration
            # will create a new device for the new controller, on the first reload,
            # but not immediately remove the old device.
            await self.hass.config_entries.async_reload(config_entry.entry_id)

        finally:
            for unsub in unsubs:
                unsub()


class ZWaveJSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Z-Wave JS."""

    @cached_property
    def _addon_setup(self) -> AddonFlowManager:
        """Return the add-on flow manager."""
        return AddonFlowManager(self.hass)

    @cached_property
    def _migration(self) -> NvmMigrationManager:
        """Return the NVM migration manager."""
        return NvmMigrationManager(self.hass)

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        self.security_keys = SecurityKeys()
        self.usb_path: str | None = None
        self.socket_path: str | None = None  # ESPHome socket
        self.ws_address: str | None = None
        # If we install the add-on we should uninstall it on entry remove.
        self.integration_created_addon = False
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.version_info: VersionInfo | None = None
        self.revert_reason: str | None = None
        self.backup_task: asyncio.Task | None = None
        self.restore_backup_task: asyncio.Task | None = None
        self.use_addon = False
        self._addon_config_updates: dict[str, Any] = {}
        self._migrating = False
        self._reconfigure_config_entry: ZwaveJSConfigEntry | None = None
        self._adapter_discovered = False
        self._recommended_install = False
        self._rf_region: str | None = None
        self._entry_unloaded_by_flow = False
        # The steps to continue with after the add-on is installed or started.
        # The reconfigure and migration flows override these.
        self._addon_configure_step = "configure_addon_user"
        self._addon_finish_step = "finish_addon_setup_user"
        # Set if the flow unique id is a placeholder that must be replaced
        # with the home ID before a config entry is created.
        self._unique_id_is_placeholder = False

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Z-Wave JS add-on."""
        if not self.install_task:
            self.install_task = self.hass.async_create_task(
                self._addon_setup.async_install_addon()
            )

        if not self.install_task.done():
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                progress_task=self.install_task,
            )

        try:
            await self.install_task
        except AddonError as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None

        self.integration_created_addon = True

        return self.async_show_progress_done(next_step_id=self._addon_configure_step)

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on installation failed."""
        return self.async_abort(reason="addon_install_failed")

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start Z-Wave JS add-on."""
        if self.hass.config.country is None and (
            not self._rf_region or self._rf_region == "Automatic"
        ):
            # If the country is not set, we need to check the RF region add-on config.
            addon_info = await self._addon_setup.async_get_addon_info()
            rf_region: str | None = addon_info.options.get(CONF_ADDON_RF_REGION)
            self._rf_region = rf_region
            if rf_region is None or rf_region == "Automatic":
                # If the RF region is not set, we need to ask the user to select it.
                return await self.async_step_rf_region()
        if (
            self._reconfigure_config_entry is None
            and self._addon_owned_by_other_entry()
        ):
            # An add-on based entry was created while this flow was open,
            # e.g. by a concurrent discovery flow. Abort before this flow
            # overwrites the add-on config of that entry.
            return self.async_abort(reason="addon_already_configured")

        if config_updates := self._addon_config_updates:
            # If we have updates to the add-on config,
            # set them before starting the add-on.
            self._addon_config_updates = {}
            await self._addon_setup.async_set_addon_config(config_updates)

        if not self.start_task:
            self.start_task = self.hass.async_create_task(self._async_start_addon())

        if not self.start_task.done():
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                progress_task=self.start_task,
            )

        try:
            await self.start_task
        except (CannotConnect, AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self.start_task = None

        return self.async_show_progress_done(next_step_id=self._addon_finish_step)

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on start failed."""
        if self._migrating:
            return self.async_abort(reason="addon_start_failed")
        if self._reconfigure_config_entry:
            return await self.async_revert_addon_config(reason="addon_start_failed")
        return self.async_abort(reason="addon_start_failed")

    async def _async_start_addon(self) -> None:
        """Start the Z-Wave JS add-on."""
        self.version_info = None
        (
            self.ws_address,
            self.version_info,
        ) = await self._addon_setup.async_start_addon_and_wait(self.ws_address)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if is_hassio(self.hass):
            return await self.async_step_installation_type()

        return await self.async_step_manual()

    async def async_step_installation_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the installation type step."""
        return self.async_show_menu(
            step_id="installation_type",
            menu_options=[
                "intent_recommended",
                "intent_custom",
            ],
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm if we are migrating adapters or just re-configuring."""
        self._reconfigure_config_entry = self._get_reconfigure_entry()
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "intent_reconfigure",
                "intent_migrate",
            ],
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        try:
            home_id = int(discovery_info.properties["homeId"])
        except KeyError, TypeError, ValueError:
            # A valueless homeId TXT record decodes to None.
            return self.async_abort(reason="invalid_discovery_info")
        await self.async_set_unique_id(str(home_id))
        self._abort_if_unique_id_configured()
        self.ws_address = f"ws://{discovery_info.host}:{discovery_info.port}"
        home_id_display = format_home_id_for_display(home_id)
        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: (
                        f"Network {home_id_display} at "
                        f"{discovery_info.host}:{discovery_info.port}"
                    )
                }
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if user_input is not None:
            # An entry with this home ID may have been configured while
            # the discovery was pending, e.g. via the add-on discovery.
            # Abort instead of converting that entry to a manual server
            # connection in the manual step.
            self._abort_if_unique_id_configured()
            return await self.async_step_manual({CONF_URL: self.ws_address})

        assert self.ws_address
        assert self.unique_id
        home_id_display = format_home_id_for_display(int(self.unique_id))
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "home_id": home_id_display,
                CONF_URL: self.ws_address[5:],
            },
        )

    @override
    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB Discovery."""
        if not is_hassio(self.hass):
            return self.async_abort(reason="discovery_requires_supervisor")
        if any(
            flow
            for flow in self._async_in_progress()
            if flow["context"].get("source") not in (SOURCE_USB, SOURCE_ZEROCONF)
        ):
            # Allow multiple USB discovery flows to be in progress.
            # Migration requires more than one USB stick to be connected,
            # which can cause more than one discovery flow to be in progress,
            # at least for a short time.
            # Zeroconf flows never touch the add-on,
            # so an idle discovery prompt should not block USB discovery.
            return self.async_abort(reason="already_in_progress")
        if current_config_entries := self._async_current_entries(include_ignore=False):
            self._reconfigure_config_entry = next(
                (
                    entry
                    for entry in current_config_entries
                    if entry.data.get(CONF_USE_ADDON)
                ),
                None,
            )
            if not self._reconfigure_config_entry:
                return self.async_abort(
                    reason="addon_required",
                    description_placeholders={
                        "zwave_js_ui_migration": ZWAVE_JS_UI_MIGRATION_INSTRUCTIONS,
                    },
                )

        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        # Zooz uses this vid/pid, but so do 2652 sticks
        if vid == "10C4" and pid == "EA60" and description and "2652" in description:
            return self.async_abort(reason="not_zwave_device")

        discovery_info.device = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )

        addon_info = await self._addon_setup.async_get_addon_info()
        if (
            addon_info.state not in (AddonState.NOT_INSTALLED, AddonState.INSTALLING)
            and (addon_device := addon_info.options.get(CONF_ADDON_DEVICE)) is not None
            and await self.hass.async_add_executor_job(
                usb.get_serial_by_id, addon_device
            )
            == discovery_info.device
        ):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(
            f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"
        )
        # We don't need to check if the unique_id is already configured
        # since we will update the unique_id before finishing the flow.
        # The unique_id set above is just a temporary value to avoid
        # duplicate discovery flows.
        dev_path = discovery_info.device
        self.usb_path = dev_path
        if manufacturer == "Nabu Casa" and description == "ZWA-2 - Nabu Casa ZWA-2":
            title = "Home Assistant Connect ZWA-2"
        else:
            human_name = usb.human_readable_device_name(
                dev_path,
                serial_number,
                manufacturer,
                description,
                vid,
                pid,
            )
            title = human_name.split(" - ")[0].strip()
        self.context["title_placeholders"] = {CONF_NAME: title}

        self._adapter_discovered = True
        if current_config_entries:
            return await self.async_step_confirm_migration()

        return await self.async_step_installation_type()

    async def async_step_confirm_migration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm USB migration."""
        if user_input is not None:
            return await self.async_step_intent_migrate()
        return self.async_show_form(
            step_id="confirm_migration",
            description_placeholders={
                "adapter_name": self.context["title_placeholders"][CONF_NAME],
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=get_manual_schema({}),
                description_placeholders={
                    "example_server_url": DEFAULT_URL,
                    "server_instructions": ZWAVE_JS_SERVER_INSTRUCTIONS,
                },
            )

        errors = {}

        try:
            version_info = await validate_input(self.hass, user_input)
        except InvalidInput as err:
            errors["base"] = err.error
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(
                str(version_info.home_id), raise_on_progress=False
            )
            # Make sure we disable any add-on handling
            # if the controller is reconfigured in a manual step.
            self._abort_if_unique_id_configured(
                updates={
                    **user_input,
                    CONF_USE_ADDON: False,
                    CONF_INTEGRATION_CREATED_ADDON: False,
                }
            )
            self.ws_address = user_input[CONF_URL]
            return self._async_create_entry_from_vars()

        return self.async_show_form(
            step_id="manual",
            data_schema=get_manual_schema(user_input),
            description_placeholders={
                "example_server_url": DEFAULT_URL,
                "server_instructions": ZWAVE_JS_SERVER_INSTRUCTIONS,
            },
            errors=errors,
        )

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Receive configuration from add-on discovery info.

        This flow is triggered by the Z-Wave JS add-on.
        """
        if any(
            flow
            for flow in self._async_in_progress()
            # Zeroconf flows never touch the add-on, so an idle discovery
            # prompt should not block the add-on discovery.
            if flow["context"].get("source") != SOURCE_ZEROCONF
        ):
            return self.async_abort(reason="already_in_progress")

        if discovery_info.slug != ADDON_SLUG:
            return self.async_abort(reason="not_zwave_js_addon")

        self.ws_address = (
            f"ws://{discovery_info.config['host']}:{discovery_info.config['port']}"
        )
        try:
            version_info = await async_get_version_info(self.hass, self.ws_address)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(str(version_info.home_id))
        self._abort_if_unique_id_configured(updates={CONF_URL: self.ws_address})

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the add-on discovery."""
        if user_input is not None:
            return await self.async_step_on_supervisor(
                user_input={CONF_USE_ADDON: True}
            )

        return self.async_show_form(step_id="hassio_confirm")

    async def async_step_intent_recommended(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select recommended installation type."""
        self._recommended_install = True
        return await self.async_step_on_supervisor({CONF_USE_ADDON: True})

    async def async_step_intent_custom(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select custom installation type."""
        if self._adapter_discovered:
            return await self.async_step_on_supervisor({CONF_USE_ADDON: True})
        return await self.async_step_on_supervisor()

    async def async_step_rf_region(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle RF region selection step."""
        if user_input is not None:
            # Store the selected RF region
            self._addon_config_updates[CONF_ADDON_RF_REGION] = self._rf_region = (
                user_input["rf_region"]
            )
            return await self.async_step_start_addon()

        schema = vol.Schema(
            {
                vol.Required("rf_region"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=RF_REGIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="rf_region",
            data_schema=schema,
        )

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host.

        When the add-on is running, we copy over it's settings.
        We will ignore settings for USB/Socket if those were discovered.

        If add-on is not running, we will configure the add-on.

        When it's not installed, we install it with new config options.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
            )
        if not user_input[CONF_USE_ADDON]:
            return await self.async_step_manual()

        self.use_addon = True

        if self._addon_owned_by_other_entry():
            # The add-on can only connect to a single adapter, so abort before
            # the flow changes the add-on config of the existing entry.
            return self.async_abort(reason="addon_already_configured")

        addon_info = await self._addon_setup.async_get_addon_info()

        if addon_info.state is AddonState.RUNNING:
            addon_config = addon_info.options
            # Use the options set by USB/ESPHome discovery
            if not self._adapter_discovered:
                self.usb_path = addon_config.get(CONF_ADDON_DEVICE)
                self.socket_path = addon_config.get(CONF_ADDON_SOCKET)

            self.security_keys = SecurityKeys.from_addon_config(addon_config)

            if self._adapter_discovered and (
                addon_config.get(CONF_ADDON_DEVICE) != self.usb_path
                or addon_config.get(CONF_ADDON_SOCKET) != self.socket_path
            ):
                # Apply the discovered adapter to the add-on config and
                # restart the add-on before connecting, so the server
                # version info reflects the discovered adapter.
                self._addon_config_updates.update(
                    {
                        CONF_ADDON_DEVICE: self.usb_path,
                        CONF_ADDON_SOCKET: self.socket_path,
                    }
                )
                return await self.async_step_start_addon()

            return await self.async_step_finish_addon_setup_user()

        if addon_info.state is AddonState.NOT_RUNNING:
            return await self.async_step_configure_addon_user()

        return await self.async_step_install_addon()

    async def async_step_configure_addon_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for config for Z-Wave JS add-on."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self.usb_path = user_input.get(CONF_USB_PATH) or None
            self.socket_path = user_input.get(CONF_SOCKET_PATH) or None
            if error := self._validate_usb_or_socket_path():
                errors["base"] = error
            else:
                return await self.async_step_network_type()

        if self._adapter_discovered:
            return await self.async_step_network_type()

        try:
            ports = await async_get_usb_ports(self.hass)
        except OSError as err:
            _LOGGER.error("Failed to get USB ports: %s", err)
            return self.async_abort(reason="usb_ports_failed")

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USB_PATH, description={"suggested_value": self.usb_path}
                ): vol.In(ports),
                vol.Optional(
                    CONF_SOCKET_PATH,
                    description={"suggested_value": self.socket_path or ""},
                ): str,
            }
        )

        return self.async_show_form(
            step_id="configure_addon_user", data_schema=data_schema, errors=errors
        )

    @callback
    def _addon_owned_by_other_entry(self) -> bool:
        """Return if another config entry uses the add-on."""
        return any(
            entry.data.get(CONF_USE_ADDON) and entry.unique_id != self.unique_id
            for entry in self._async_current_entries(include_ignore=False)
        )

    @callback
    def _validate_usb_or_socket_path(self) -> str | None:
        """Validate that exactly one of USB path and socket path is set."""
        if self.usb_path and self.socket_path:
            return "usb_and_socket_path"
        if not self.usb_path and not self.socket_path:
            return "missing_usb_or_socket_path"
        return None

    async def async_step_network_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for network type (new or existing)."""
        # For recommended installation, automatically set network type to "new"
        if self._recommended_install:
            user_input = {"network_type": NETWORK_TYPE_NEW}

        if user_input is not None:
            if user_input["network_type"] == NETWORK_TYPE_NEW:
                addon_info = await self._addon_setup.async_get_addon_info()
                # Keep existing keys from the add-on config so the keys of a
                # previously configured network are not destroyed.
                # Keys left empty are generated by the add-on on start.
                self.security_keys = SecurityKeys.from_addon_config(addon_info.options)

                self._addon_config_updates = {
                    CONF_ADDON_DEVICE: self.usb_path,
                    CONF_ADDON_SOCKET: self.socket_path,
                    **self.security_keys.to_addon_config(),
                }
                return await self.async_step_start_addon()

            # Network already exists, go to security keys step
            return await self.async_step_configure_security_keys()

        return self.async_show_form(
            step_id="network_type",
            data_schema=vol.Schema(
                {
                    vol.Required("network_type", default=""): vol.In(
                        [NETWORK_TYPE_NEW, NETWORK_TYPE_EXISTING]
                    )
                }
            ),
        )

    async def async_step_configure_security_keys(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for security keys for existing Z-Wave network."""
        addon_info = await self._addon_setup.async_get_addon_info()
        default_keys = SecurityKeys.from_addon_config(
            addon_info.options, self.security_keys
        )

        if user_input is not None:
            self.security_keys = default_keys.updated_from_user_input(user_input)

            self._addon_config_updates = {
                CONF_ADDON_DEVICE: self.usb_path,
                CONF_ADDON_SOCKET: self.socket_path,
                **self.security_keys.to_addon_config(),
            }
            return await self.async_step_start_addon()

        data_schema = vol.Schema(
            {
                vol.Optional(entry_key, default=getattr(default_keys, field)): str
                for field, _, entry_key in KEY_FIELDS
            }
        )

        return self.async_show_form(
            step_id="configure_security_keys", data_schema=data_schema
        )

    async def async_step_finish_addon_setup_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry.

        Get add-on discovery info and server version info.
        Set unique id and abort if already configured.
        """
        if not self.ws_address:
            discovery_info = await self._addon_setup.async_get_addon_discovery_info()
            self.ws_address = f"ws://{discovery_info['host']}:{discovery_info['port']}"

        if (
            not self.unique_id
            or self.source == SOURCE_USB
            or self._unique_id_is_placeholder
        ):
            if not self.version_info:
                try:
                    self.version_info = await async_get_version_info(
                        self.hass, self.ws_address
                    )
                except CannotConnect as err:
                    raise AbortFlow("cannot_connect") from err

            await self.async_set_unique_id(
                str(self.version_info.home_id), raise_on_progress=False
            )
            self._unique_id_is_placeholder = False

        self._abort_if_unique_id_configured(
            updates={
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_SOCKET_PATH: self.socket_path,
                **self.security_keys.to_entry_data(),
            },
            error=(
                "migration_successful"
                if self.source in (SOURCE_USB, SOURCE_ESPHOME)
                else "already_configured"
            ),
        )
        return self._async_create_entry_from_vars()

    @callback
    def _async_create_entry_from_vars(self) -> ConfigFlowResult:
        """Return a config entry for the flow."""
        if self.use_addon and self._addon_owned_by_other_entry():
            # The add-on can only connect to a single adapter,
            # so only one config entry may use the add-on.
            return self.async_abort(reason="addon_already_configured")

        self._async_abort_other_prompt_flows()

        return self.async_create_entry(
            title=TITLE,
            data={
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_SOCKET_PATH: self.socket_path,
                **self.security_keys.to_entry_data(),
                CONF_USE_ADDON: self.use_addon,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
        )

    @callback
    def _async_update_entry(self, updates: dict[str, Any]) -> None:
        """Update the config entry with new data."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        self.hass.config_entries.async_update_entry(
            config_entry, data=config_entry.data | updates
        )
        self._async_schedule_entry_reload()

    async def _async_unload_entry_for_flow(self) -> None:
        """Unload the config entry being reconfigured for this flow.

        The entry is reloaded when the flow is removed,
        unless a flow step schedules a reload itself.
        """
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        self._entry_unloaded_by_flow = True
        await self.hass.config_entries.async_unload(config_entry.entry_id)

    @callback
    def _async_schedule_entry_reload(self) -> None:
        """Schedule a reload of the config entry being reconfigured."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        self._entry_unloaded_by_flow = False
        self.hass.config_entries.async_schedule_reload(config_entry.entry_id)

    @callback
    @override
    def async_remove(self) -> None:
        """Reload the config entry if the flow unloaded it and left it down.

        This recovers the entry when a flow that has unloaded it,
        e.g. a migration waiting for the adapter to be unplugged,
        is aborted or abandoned.
        """
        if not self._entry_unloaded_by_flow:
            return
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if (
            # The entry may have been removed while the flow was pending.
            self.hass.config_entries.async_get_entry(config_entry.entry_id) is None
            or config_entry.state is not ConfigEntryState.NOT_LOADED
        ):
            return
        if (original_config := self._addon_setup.original_config) is not None:
            # The flow changed the add-on config without completing.
            # Restore the config before reloading the entry, so the entry
            # doesn't adopt the unconfirmed adapter and keys on setup.
            self.hass.async_create_task(
                self._async_restore_addon_config_and_reload(original_config)
            )
            return
        self.hass.config_entries.async_schedule_reload(config_entry.entry_id)

    async def _async_restore_addon_config_and_reload(
        self, original_config: dict[str, Any]
    ) -> None:
        """Restore the add-on config and reload the config entry."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        addon_manager = self._addon_setup.addon_manager
        # Migrate the legacy network key, like async_set_addon_config does,
        # so restoring doesn't drop the S0 key on older add-on configurations.
        restored_config = migrate_network_key(original_config)
        try:
            await addon_manager.async_set_addon_options(restored_config)
        except AddonError as err:
            # Don't reload the entry if the options were not restored, so the
            # reload doesn't adopt the unconfirmed options still on the add-on.
            _LOGGER.error("Failed to restore add-on options: %s", err)
            return
        if self._addon_setup.restart_addon or self._addon_setup.addon_started:
            # The add-on is running with the unconfirmed options this flow set,
            # either because it was already running or because this flow started
            # it. Schedule a restart to apply the restored options, so the entry
            # doesn't reconnect to the unconfirmed adapter. Don't await it, to
            # avoid re-raising the cancellation of the flow's own start task.
            addon_manager.async_schedule_restart_addon(catch_error=True)
        self.hass.config_entries.async_schedule_reload(config_entry.entry_id)

    async def async_step_intent_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        self._addon_configure_step = "configure_addon_reconfigure"
        self._addon_finish_step = "finish_addon_setup_reconfigure"
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor_reconfigure()

        return await self.async_step_manual_reconfigure()

    async def async_step_intent_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the user wants to reset their current controller."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if not self._adapter_discovered and not config_entry.data.get(CONF_USE_ADDON):
            return self.async_abort(
                reason="addon_required",
                description_placeholders={
                    "zwave_js_ui_migration": ZWAVE_JS_UI_MIGRATION_INSTRUCTIONS,
                },
            )

        try:
            driver = self._get_driver()
        except AbortFlow:
            return self.async_abort(reason="config_entry_not_loaded")
        if (
            sdk_version := driver.controller.sdk_version
        ) is not None and sdk_version < MIN_MIGRATION_SDK_VERSION:
            _LOGGER.warning(
                "Migration from this controller that has SDK version %s "
                "is not supported. If possible, update the firmware "
                "of the controller to a firmware built using SDK version %s or higher",
                sdk_version,
                MIN_MIGRATION_SDK_VERSION,
            )
            return self.async_abort(
                reason="migration_low_sdk_version",
                description_placeholders={
                    "ok_sdk_version": str(MIN_MIGRATION_SDK_VERSION)
                },
            )

        if any(
            flow
            for flow in self._async_in_progress()
            if flow.get("step_id") not in ABORT_SAFE_STEPS
        ):
            # Another flow, e.g. a competing migration confirmed earlier,
            # has progressed beyond a prompt. Don't start a second migration.
            return self.async_abort(reason="already_in_progress")

        # Remaining prompts, e.g. for other discovered adapters,
        # are superseded by this migration.
        self._async_abort_other_prompt_flows()

        self._migrating = True
        self._addon_finish_step = "finish_addon_setup_migrate"
        return await self.async_step_backup_nvm()

    async def async_step_backup_nvm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Backup the current network."""
        if self.backup_task is None:
            self.backup_task = self.hass.async_create_task(self._async_backup_network())

        if not self.backup_task.done():
            return self.async_show_progress(
                step_id="backup_nvm",
                progress_action="backup_nvm",
                progress_task=self.backup_task,
            )

        try:
            await self.backup_task
        except AbortFlow as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="backup_failed")
        finally:
            self.backup_task = None

        return self.async_show_progress_done(next_step_id="instruct_unplug")

    async def async_step_restore_nvm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Restore the backup."""
        if self.restore_backup_task is None:
            self.restore_backup_task = self.hass.async_create_task(
                self._async_restore_network_backup()
            )

        if not self.restore_backup_task.done():
            return self.async_show_progress(
                step_id="restore_nvm",
                progress_action="restore_nvm",
                progress_task=self.restore_backup_task,
            )

        try:
            await self.restore_backup_task
        except AbortFlow as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="restore_failed")
        finally:
            self.restore_backup_task = None

        return self.async_show_progress_done(next_step_id="migration_done")

    async def async_step_instruct_unplug(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Instruct the user to unplug the old controller."""

        if user_input is not None:
            if self._adapter_discovered:
                # Discovery was used, so the device is already known.
                self._addon_config_updates[CONF_ADDON_DEVICE] = self.usb_path
                self._addon_config_updates[CONF_ADDON_SOCKET] = self.socket_path
                return await self.async_step_start_addon()
            # Now that the old controller is gone, we can scan for serial ports again
            return await self.async_step_choose_serial_port()

        config_entry = self._reconfigure_config_entry
        assert config_entry is not None

        # Unload the config entry before asking the user to unplug the controller.
        await self._async_unload_entry_for_flow()

        return self.async_show_form(
            step_id="instruct_unplug",
            description_placeholders={
                "file_path": str(self._migration.backup_filepath),
            },
        )

    async def async_step_manual_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if user_input is None:
            return self.async_show_form(
                step_id="manual_reconfigure",
                data_schema=get_manual_schema({CONF_URL: config_entry.data[CONF_URL]}),
                description_placeholders={
                    "example_server_url": DEFAULT_URL,
                    "server_instructions": ZWAVE_JS_SERVER_INSTRUCTIONS,
                },
            )

        errors = {}

        try:
            version_info = await validate_input(self.hass, user_input)
        except InvalidInput as err:
            errors["base"] = err.error
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if config_entry.unique_id != str(version_info.home_id):
                return self.async_abort(reason="different_device")

            # Make sure we disable any add-on handling
            # if the controller is reconfigured in a manual step.
            self._async_update_entry(
                {
                    **user_input,
                    CONF_USE_ADDON: False,
                    CONF_INTEGRATION_CREATED_ADDON: False,
                }
            )

            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="manual_reconfigure",
            data_schema=get_manual_schema(user_input),
            description_placeholders={
                "example_server_url": DEFAULT_URL,
                "server_instructions": ZWAVE_JS_SERVER_INSTRUCTIONS,
            },
            errors=errors,
        )

    async def async_step_on_supervisor_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor_reconfigure",
                data_schema=get_on_supervisor_schema(
                    {CONF_USE_ADDON: config_entry.data.get(CONF_USE_ADDON, True)}
                ),
            )

        if not user_input[CONF_USE_ADDON]:
            if config_entry.data.get(CONF_USE_ADDON):
                # Unload the config entry before stopping the add-on.
                await self._async_unload_entry_for_flow()
                _LOGGER.debug("Stopping Z-Wave JS app")
                try:
                    await self._addon_setup.async_stop_addon()
                except AddonError as err:
                    _LOGGER.error(err)
                    self._async_schedule_entry_reload()
                    raise AbortFlow("addon_stop_failed") from err
            return await self.async_step_manual_reconfigure()

        addon_info = await self._addon_setup.async_get_addon_info()

        if addon_info.state is AddonState.NOT_INSTALLED:
            return await self.async_step_install_addon()

        return await self.async_step_configure_addon_reconfigure()

    async def async_step_configure_addon_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for config for Z-Wave JS add-on."""
        addon_info = await self._addon_setup.async_get_addon_info()
        addon_config = addon_info.options

        errors: dict[str, str] = {}

        if user_input is not None:
            # The revert helper only passes keys present in the original
            # add-on config, which may lack some of the security keys,
            # so treat missing keys as empty.
            self.security_keys = SecurityKeys().updated_from_user_input(user_input)
            self.usb_path = user_input.get(CONF_USB_PATH) or None
            self.socket_path = user_input.get(CONF_SOCKET_PATH) or None

            if error := self._validate_usb_or_socket_path():
                if reason := self.revert_reason:
                    # The original add-on config has no valid adapter
                    # connection to revert to, so abort instead of showing
                    # the form with an error in the middle of a revert.
                    _LOGGER.error(
                        "Cannot revert add-on config without an adapter: %s", error
                    )
                    self.revert_reason = None
                    self._async_schedule_entry_reload()
                    return self.async_abort(reason=reason)
                errors["base"] = error
            else:
                addon_config_updates = {
                    CONF_ADDON_DEVICE: self.usb_path,
                    CONF_ADDON_SOCKET: self.socket_path,
                    **self.security_keys.to_addon_config(),
                }

                addon_config_updates = self._addon_config_updates | addon_config_updates
                self._addon_config_updates = {}

                await self._addon_setup.async_set_addon_config(addon_config_updates)

                if (
                    addon_info.state is AddonState.RUNNING
                    and not self._addon_setup.restart_addon
                ):
                    return await self.async_step_finish_addon_setup_reconfigure()

                if (
                    config_entry := self._reconfigure_config_entry
                ) and config_entry.data.get(CONF_USE_ADDON):
                    # Disconnect integration before restarting add-on.
                    await self._async_unload_entry_for_flow()

                return await self.async_step_start_addon()

        usb_path = addon_config.get(CONF_ADDON_DEVICE, self.usb_path or "")
        socket_path = addon_config.get(CONF_ADDON_SOCKET, self.socket_path or "")
        default_keys = SecurityKeys.from_addon_config(addon_config, self.security_keys)

        try:
            ports = await async_get_usb_ports(self.hass)
        except OSError as err:
            _LOGGER.error("Failed to get USB ports: %s", err)
            return self.async_abort(reason="usb_ports_failed")

        # Insert empty option in ports to allow setting a socket
        ports = {
            "": "Use Socket",
            **ports,
        }

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USB_PATH, description={"suggested_value": usb_path}
                ): vol.In(ports),
                vol.Optional(
                    CONF_SOCKET_PATH, description={"suggested_value": socket_path}
                ): str,
                **{
                    vol.Optional(
                        entry_key,
                        description={"suggested_value": getattr(default_keys, field)},
                    ): str
                    for field, _, entry_key in KEY_FIELDS
                },
            }
        )

        return self.async_show_form(
            step_id="configure_addon_reconfigure",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_choose_serial_port(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a serial port."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.usb_path = user_input.get(CONF_USB_PATH) or None
            self.socket_path = user_input.get(CONF_SOCKET_PATH) or None
            if error := self._validate_usb_or_socket_path():
                errors["base"] = error
            else:
                self._addon_config_updates[CONF_ADDON_DEVICE] = self.usb_path
                self._addon_config_updates[CONF_ADDON_SOCKET] = self.socket_path
                return await self.async_step_start_addon()

        try:
            ports = await async_get_usb_ports(self.hass)
        except OSError as err:
            _LOGGER.error("Failed to get USB ports: %s", err)
            return self.async_abort(reason="usb_ports_failed")

        addon_info = await self._addon_setup.async_get_addon_info()
        addon_config = addon_info.options
        old_usb_path = addon_config.get(CONF_ADDON_DEVICE, "")
        # Remove the old controller from the ports list.
        ports.pop(
            await self.hass.async_add_executor_job(usb.get_serial_by_id, old_usb_path),
            None,
        )
        # Insert empty option in ports to allow setting a socket
        ports = {
            "": "Use Socket",
            **ports,
        }

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_USB_PATH): vol.In(ports),
                vol.Optional(CONF_SOCKET_PATH): str,
            }
        )
        return self.async_show_form(
            step_id="choose_serial_port", data_schema=data_schema, errors=errors
        )

    async def async_step_backup_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Backup failed."""
        return self.async_abort(reason="backup_failed")

    async def async_step_restore_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Restore failed."""
        if user_input is not None:
            return await self.async_step_restore_nvm()
        backup_filepath = self._migration.backup_filepath
        backup_data = self._migration.backup_data
        assert backup_filepath is not None
        assert backup_data is not None

        return self.async_show_form(
            step_id="restore_failed",
            description_placeholders={
                "file_path": str(backup_filepath),
                "file_url": (
                    "data:application/octet-stream;base64,"
                    f"{base64.b64encode(backup_data).decode('ascii')}"
                ),
                "file_name": backup_filepath.name,
            },
        )

    async def async_step_migration_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Migration done."""
        self._async_abort_other_prompt_flows()
        return self.async_abort(reason="migration_successful")

    @callback
    def _async_abort_other_prompt_flows(self) -> None:
        """Abort other flows that are only showing a prompt.

        A created entry or a finished migration may make them redundant.
        Flows that have progressed further, e.g. a migration that has
        backed up the network, must not be interrupted.
        """
        for progress in self._async_in_progress():
            if progress.get("step_id") in ABORT_SAFE_STEPS:
                self.hass.config_entries.flow.async_abort(progress["flow_id"])

    async def async_step_finish_addon_setup_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry update."""
        ws_address = self.ws_address
        assert ws_address is not None
        version_info = self.version_info
        assert version_info is not None
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None

        # We need to wait for the config entry to be reloaded,
        # before restoring the backup.
        # We will do this in the restore nvm progress task,
        # to get a nicer user experience.
        self.hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                CONF_URL: ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_SOCKET_PATH: self.socket_path,
                **self.security_keys.to_entry_data(),
                CONF_USE_ADDON: True,
                # Keep the entry's add-on ownership if it installed the add-on.
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon
                or config_entry.data.get(CONF_INTEGRATION_CREATED_ADDON, False),
            },
            unique_id=str(version_info.home_id),
        )

        return await self.async_step_restore_nvm()

    async def async_step_finish_addon_setup_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry update.

        Get add-on discovery info and server version info.
        Check for same unique id and abort if not the same unique id.
        """
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if self.revert_reason:
            self._addon_setup.original_config = None
            reason = self.revert_reason
            self.revert_reason = None
            return await self.async_revert_addon_config(reason=reason)

        if not self.ws_address:
            discovery_info = await self._addon_setup.async_get_addon_discovery_info()
            self.ws_address = f"ws://{discovery_info['host']}:{discovery_info['port']}"

        if not self.version_info:
            try:
                self.version_info = await async_get_version_info(
                    self.hass, self.ws_address
                )
            except CannotConnect:
                return await self.async_revert_addon_config(reason="cannot_connect")

        if config_entry.unique_id != str(self.version_info.home_id):
            return await self.async_revert_addon_config(reason="different_device")

        self._async_update_entry(
            {
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_SOCKET_PATH: self.socket_path,
                **self.security_keys.to_entry_data(),
                CONF_USE_ADDON: True,
                # Keep the entry's add-on ownership if it installed the add-on.
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon
                or config_entry.data.get(CONF_INTEGRATION_CREATED_ADDON, False),
            }
        )

        return self.async_abort(reason="reconfigure_successful")

    async def async_step_esphome(
        self, discovery_info: ESPHomeServiceInfo
    ) -> ConfigFlowResult:
        """Handle a ESPHome discovery."""
        if not is_hassio(self.hass):
            return self.async_abort(reason="not_hassio")

        if any(
            flow
            for flow in self._async_in_progress()
            if flow["context"].get("source") != SOURCE_ZEROCONF
            and flow.get("step_id") not in ABORT_SAFE_STEPS
        ):
            # Another flow is past the point of only showing a prompt,
            # e.g. a migration that has backed up the network.
            # This discovery may change the shared add-on config,
            # so don't interfere. ESPHome fires the discovery again
            # on the next device reconnect.
            return self.async_abort(reason="already_in_progress")

        if discovery_info.zwave_home_id:
            existing_entry: ConfigEntry | None = None
            if (
                (
                    current_config_entries := self._async_current_entries(
                        include_ignore=False
                    )
                )
                and (home_id := str(discovery_info.zwave_home_id))
                and (
                    existing_entry := next(
                        (
                            entry
                            for entry in current_config_entries
                            if entry.unique_id == home_id
                        ),
                        None,
                    )
                )
            ):
                # We can't migrate entries that are not using the add-on
                if not existing_entry.data.get(CONF_USE_ADDON):
                    return self.async_abort(reason="already_configured")

                # Only update config automatically if using socket
                if existing_entry.data.get(CONF_SOCKET_PATH):
                    addon_info = await self._addon_setup.async_get_addon_info()
                    if (
                        existing_entry.data[CONF_SOCKET_PATH]
                        == discovery_info.socket_path
                        # The add-on may have been repointed externally,
                        # in which case the config needs to be repaired.
                        and addon_info.options.get(CONF_ADDON_SOCKET)
                        == discovery_info.socket_path
                        and addon_info.options.get(CONF_ADDON_DEVICE) is None
                    ):
                        # The ESPHome device fires discovery on every
                        # reconnect, so don't touch the add-on config or
                        # reload the entry if nothing changed.
                        return self.async_abort(reason="already_configured")
                    await self._addon_setup.async_set_addon_config(
                        {
                            CONF_ADDON_DEVICE: None,
                            CONF_ADDON_SOCKET: discovery_info.socket_path,
                        }
                    )
                    if self._addon_setup.restart_addon:
                        await self._addon_setup.async_stop_addon()
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data={
                            **existing_entry.data,
                            CONF_SOCKET_PATH: discovery_info.socket_path,
                        },
                    )
                    self.hass.config_entries.async_schedule_reload(
                        existing_entry.entry_id
                    )
                    return self.async_abort(reason="already_configured")

        # The adapter may first be discovered without a home ID and get the
        # placeholder unique id below, then report a home ID on a later
        # discovery. Track the placeholder id so such a discovery can be
        # deduplicated against a pending prompt or an ignored entry.
        placeholder_unique_id = f"esphome_{discovery_info.name}"
        if discovery_info.zwave_home_id:
            # We are not aborting if home ID configured
            # here, we just want to make sure that it's set.
            # We will update a USB based config entry
            # automatically in
            # `async_step_finish_addon_setup_user`.
            if any(
                flow["context"].get("unique_id") == placeholder_unique_id
                for flow in self._async_in_progress()
            ):
                return self.async_abort(reason="already_in_progress")
            # Raise on progress to avoid a duplicate prompt when the same
            # adapter is rediscovered, e.g. with a new IP address.
            await self.async_set_unique_id(str(discovery_info.zwave_home_id))
        else:
            # Set a placeholder unique id so the discovery can be ignored
            # also when the adapter doesn't report a home ID yet.
            # It is replaced with the home ID before an entry is created.
            self._unique_id_is_placeholder = True
            await self.async_set_unique_id(placeholder_unique_id)

        if any(
            entry.source == SOURCE_IGNORE
            and entry.unique_id in (self.unique_id, placeholder_unique_id)
            for entry in self._async_current_entries(include_ignore=True)
        ):
            return self.async_abort(reason="already_configured")

        self.socket_path = discovery_info.socket_path
        home_id_display = format_home_id_for_display(discovery_info.zwave_home_id)
        self.context["title_placeholders"] = {
            CONF_NAME: f"Network {home_id_display} via {discovery_info.name} (ESPHome)"
        }
        self._adapter_discovered = True

        # A discovered adapter that doesn't belong to an existing add-on based
        # entry is a different adapter, so offer to migrate the existing
        # network to it instead of repointing the shared add-on config.
        discovered_home_id = (
            str(discovery_info.zwave_home_id) if discovery_info.zwave_home_id else None
        )
        if addon_entry := next(
            (
                entry
                for entry in self._async_current_entries(include_ignore=False)
                if entry.data.get(CONF_USE_ADDON)
                and entry.unique_id != discovered_home_id
            ),
            None,
        ):
            self._reconfigure_config_entry = addon_entry
            return await self.async_step_confirm_migration()

        return await self.async_step_installation_type()

    async def async_revert_addon_config(self, reason: str) -> ConfigFlowResult:
        """Abort the options flow.

        If the add-on options have been changed, revert those and restart add-on.
        """
        # If reverting the add-on options failed, abort immediately.
        if self.revert_reason:
            _LOGGER.error(
                "Failed to revert add-on options before aborting flow, reason: %s",
                reason,
            )

        if self.revert_reason or not self._addon_setup.original_config:
            config_entry = self._reconfigure_config_entry
            assert config_entry is not None
            self._async_schedule_entry_reload()
            return self.async_abort(reason=reason)

        self.revert_reason = reason
        # Migrate a legacy network key so it is reverted as the S0 legacy key,
        # which is what ADDON_USER_INPUT_MAP knows about.
        original_config = migrate_network_key(self._addon_setup.original_config)
        addon_config_input = {
            ADDON_USER_INPUT_MAP[addon_key]: addon_val
            for addon_key, addon_val in original_config.items()
            if addon_key in ADDON_USER_INPUT_MAP
        }
        _LOGGER.debug("Reverting app options, reason: %s", reason)
        return await self.async_step_configure_addon_reconfigure(addon_config_input)

    async def _async_backup_network(self) -> None:
        """Backup the current network."""
        await self._migration.async_backup(
            self._get_driver(), self.async_update_progress
        )

    async def _async_restore_network_backup(self) -> None:
        """Restore the backup."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        await self._migration.async_restore(
            config_entry, self._get_driver, self.async_update_progress
        )

    def _get_driver(self) -> Driver:
        """Get the driver from the config entry."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if config_entry.state is not ConfigEntryState.LOADED:
            raise AbortFlow("Configuration entry is not loaded")
        client: Client = config_entry.runtime_data.client
        assert client.driver is not None
        return client.driver


class InvalidInput(HomeAssistantError):
    """Error to indicate input data is invalid."""

    def __init__(self, error: str) -> None:
        """Initialize error."""
        super().__init__()
        self.error = error
