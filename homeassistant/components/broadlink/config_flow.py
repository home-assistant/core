"""Config flow for Broadlink devices."""

import asyncio
from collections.abc import Mapping
import errno
import logging
import socket
from typing import Any, override
from urllib.parse import urlencode, urlparse

import broadlink_async as blk
from broadlink_async.exceptions import (
    AuthenticationError,
    BroadlinkException,
    NetworkTimeoutError,
)
from broadlink_async.magic import DiscoveredRMMax, Family
from broadlink_async.magic.const import RM_MAX_DEVTYPE
import probatio

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_TIMEOUT, CONF_TYPE
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_ENTRY_KIND,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEVICE_TYPES,
    DOMAIN,
    ENTRY_KIND_MAGIC_FAMILY,
    IMPORT_PATH,
    IMPORT_TIMEOUT,
    is_magic_entry,
)
from .helpers import format_mac
from .magic_gateway_listener import DATA_GATEWAY_LISTENER, async_get_gateway_listener
from .magic_helpers import family_to_entry_data, gateways_from_entry_data
from .magic_import_session import ImportSession, get_import_manager
from .magic_import_view import async_register_import_view

_LOGGER = logging.getLogger(__name__)


class BroadlinkFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Broadlink config flow."""

    VERSION = 1

    device: blk.Device
    _session: ImportSession | None = None
    _import_task: asyncio.Task[None] | None = None
    _family: Family | None = None
    _gateways: list[DiscoveredRMMax] | None = None
    _existing_entry: ConfigEntry | None = None
    _timeout_shown = False

    @override
    @callback
    def async_remove(self) -> None:
        """Close the device's socket when the flow ends, however it ends.

        The device created for the flow is only used to probe and
        authenticate; the config entry builds its own.
        """
        if (device := getattr(self, "device", None)) is not None:
            self.hass.async_create_task(device.aclose())
        if self._session is not None:
            get_import_manager(self.hass).remove(self._session.project_id)
            self._session = None
        if manager := self.hass.data.get(DATA_GATEWAY_LISTENER):
            self.hass.async_create_task(
                manager.async_release_flow(self.flow_id),
                f"{DOMAIN} release Magic config flow listener",
            )

    async def async_set_device(
        self, device: blk.Device, raise_on_progress: bool = True
    ) -> None:
        """Define a device for the config flow."""
        if device.type not in DEVICE_TYPES:
            _LOGGER.error(
                (
                    "Unsupported device: %s. If it worked before, please open "
                    "an issue at https://github.com/home-assistant/core/issues"
                ),
                hex(device.devtype),
            )
            raise AbortFlow("not_supported")

        await self.async_set_unique_id(
            device.mac.hex(), raise_on_progress=raise_on_progress
        )
        # A probe replaced after a failed auth() has an open endpoint.
        previous = getattr(self, "device", None)
        if previous is not None and previous is not device:
            await previous.aclose()
        self.device = device

        self.context["title_placeholders"] = {
            "name": device.name or device.model,
            "model": device.model,
            "host": device.host[0],
        }

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        host = discovery_info.ip
        unique_id = discovery_info.macaddress.lower().replace(":", "")
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            device = await blk.hello(host)

        except NetworkTimeoutError:
            return self.async_abort(reason="cannot_connect")

        except OSError as err:
            if err.errno == errno.ENETUNREACH:
                return self.async_abort(reason="cannot_connect")
            return self.async_abort(reason="unknown")

        if device.type not in DEVICE_TYPES:
            return self.async_abort(reason="not_supported")

        await self.async_set_device(device)
        return await self.async_step_auth()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select the Broadlink setup mode."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["device", "magic_family"],
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup of a classic Broadlink device."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

            try:
                device = await blk.hello(host, timeout=timeout)

            except NetworkTimeoutError:
                errors["base"] = "cannot_connect"
                err_msg = "Device not found"

            except OSError as err:
                if err.errno in {errno.EINVAL, socket.EAI_NONAME}:
                    errors["base"] = "invalid_host"
                    err_msg = "Invalid hostname or IP address"
                elif err.errno == errno.ENETUNREACH:
                    errors["base"] = "cannot_connect"
                    err_msg = str(err)
                else:
                    errors["base"] = "unknown"
                    err_msg = str(err)

            else:
                device.timeout = timeout

                if self.source != SOURCE_REAUTH:
                    await self.async_set_device(device)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: device.host[0], CONF_TIMEOUT: timeout}
                    )
                    return await self.async_step_auth()

                if device.mac == self.device.mac:
                    await self.async_set_device(device, raise_on_progress=False)
                    return await self.async_step_auth()

                errors["base"] = "invalid_host"
                err_msg = (
                    "This is not the device you are looking for. The MAC "
                    f"address must be {format_mac(self.device.mac)}"
                )

            _LOGGER.error("Failed to connect to the device at %s: %s", host, err_msg)

            if self.source == SOURCE_IMPORT:
                return self.async_abort(reason=errors["base"])

        data_schema = {
            probatio.Required(CONF_HOST): str,
            probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        }
        return self.async_show_form(
            step_id="device",
            data_schema=probatio.Schema(data_schema),
            errors=errors,
        )

    async def async_step_auth(self) -> ConfigFlowResult:
        """Authenticate to the device."""
        device = self.device
        errors: dict[str, str] = {}

        try:
            await device.auth()

        except AuthenticationError:
            errors["base"] = "invalid_auth"
            await self.async_set_unique_id(device.mac.hex())
            return await self.async_step_reset(errors=errors)

        except NetworkTimeoutError as err:
            errors["base"] = "cannot_connect"
            err_msg = str(err)

        except BroadlinkException as err:
            errors["base"] = "unknown"
            err_msg = str(err)

        except OSError as err:
            if err.errno == errno.ENETUNREACH:
                errors["base"] = "cannot_connect"
                err_msg = str(err)
            else:
                errors["base"] = "unknown"
                err_msg = str(err)

        else:
            await self.async_set_unique_id(device.mac.hex())
            if device.is_locked:
                if self.source == SOURCE_IMPORT:
                    _LOGGER.warning(
                        (
                            "%s (%s at %s) is ready to be configured. Click "
                            "Configuration in the sidebar, click Integrations and "
                            "click Configure on the device to complete the setup"
                        ),
                        device.name or device.model,
                        device.model,
                        device.host[0],
                    )
                return await self.async_step_unlock()
            return await self.async_step_finish()

        await self.async_set_unique_id(device.mac.hex())
        _LOGGER.error(
            "Failed to authenticate to the device at %s: %s", device.host[0], err_msg
        )
        return self.async_show_form(step_id="auth", errors=errors)

    async def async_step_reset(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Guide the user to unlock the device manually.

        We are unable to authenticate because the device is locked.
        The user needs to open the Broadlink app and unlock the device.
        """
        device = self.device

        if user_input is None:
            return self.async_show_form(
                step_id="reset",
                errors=errors,
                description_placeholders={
                    "name": device.name or device.model,
                    "model": device.model,
                    "host": device.host[0],
                },
            )

        return await self.async_step_device(
            {CONF_HOST: device.host[0], CONF_TIMEOUT: device.timeout}
        )

    async def async_step_unlock(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Unlock the device.

        The authentication succeeded, but the device is locked.
        We can offer an unlock to prevent authorization errors.
        """
        device = self.device
        errors = {}

        if user_input is None:
            pass

        elif user_input["unlock"]:
            try:
                await device.set_lock(False)

            except NetworkTimeoutError as err:
                errors["base"] = "cannot_connect"
                err_msg = str(err)

            except BroadlinkException as err:
                errors["base"] = "unknown"
                err_msg = str(err)

            except OSError as err:
                if err.errno == errno.ENETUNREACH:
                    errors["base"] = "cannot_connect"
                    err_msg = str(err)
                else:
                    errors["base"] = "unknown"
                    err_msg = str(err)

            else:
                return await self.async_step_finish()

            _LOGGER.error(
                "Failed to unlock the device at %s: %s", device.host[0], err_msg
            )

        else:
            return await self.async_step_finish()

        data_schema = {probatio.Required("unlock", default=False): bool}
        return self.async_show_form(
            step_id="unlock",
            errors=errors,
            data_schema=probatio.Schema(data_schema),
            description_placeholders={
                "name": device.name or device.model,
                "model": device.model,
                "host": device.host[0],
            },
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry."""
        device = self.device

        # Abort reauthentication flow.
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: device.host[0], CONF_TIMEOUT: device.timeout}
        )

        return self.async_create_entry(
            title=device.name or device.model,
            data={
                CONF_HOST: device.host[0],
                CONF_MAC: device.mac.hex(),
                CONF_TYPE: device.devtype,
                CONF_TIMEOUT: device.timeout,
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a device."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        return await self.async_step_device(import_data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauthenticate to the device."""
        device = blk.gendevice(
            entry_data[CONF_TYPE],
            (entry_data[CONF_HOST], DEFAULT_PORT),
            bytes.fromhex(entry_data[CONF_MAC]),
            name=self._get_reauth_entry().title,
        )
        device.timeout = entry_data[CONF_TIMEOUT]
        await self.async_set_device(device)
        return await self.async_step_reset()

    def _new_magic_session(self) -> ImportSession:
        """Replace and return the transient Magic import session."""
        if self._session is not None:
            get_import_manager(self.hass).remove(self._session.project_id)
        self._session = get_import_manager(self.hass).create(self.flow_id)
        return self._session

    def _magic_import_url(self, session: ImportSession) -> str:
        """Build the App-compatible one-time family import URL."""
        base_url = get_url(
            self.hass,
            allow_internal=True,
            allow_external=True,
            allow_cloud=False,
            prefer_external=False,
        ).rstrip("/")
        host = urlparse(base_url).hostname or ""
        query = urlencode(
            {
                "projectid": session.project_id,
                "sharetype": "saas_carpark",
                "devaddr": host,
            }
        )
        return f"{base_url}{IMPORT_PATH}?{query}"

    async def async_step_magic_family(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display a one-time Magic Home family import QR code."""
        async_register_import_view(self.hass)
        try:
            listener = await async_get_gateway_listener(self.hass)
        except OSError:
            return self.async_abort(reason="cannot_listen")
        listener.acquire_flow(self.flow_id)
        if self._session is None:
            self._new_magic_session()
        assert self._session is not None

        try:
            import_url = self._magic_import_url(self._session)
        except NoURLAvailableError:
            return self.async_abort(reason="no_url")

        if user_input is not None:
            return await self.async_step_magic_wait_for_import()

        return self.async_show_form(
            step_id="magic_family",
            data_schema=probatio.Schema(
                {
                    probatio.Optional("qr"): selector.QrCodeSelector(
                        selector.QrCodeSelectorConfig(
                            data=import_url,
                            scale=5,
                            error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                        )
                    )
                }
            ),
            description_placeholders={"import_url": import_url},
        )

    async def _async_wait_for_magic_import(self) -> None:
        """Wait for the Magic Home app upload."""
        assert self._session is not None
        async with asyncio.timeout(IMPORT_TIMEOUT):
            await self._session.event.wait()

    async def async_step_magic_wait_for_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the Magic Home app to upload a family."""
        if self._import_task is None:
            self._import_task = self.hass.async_create_task(
                self._async_wait_for_magic_import()
            )

        if not self._import_task.done():
            return self.async_show_progress(
                step_id="magic_wait_for_import",
                progress_action="magic_wait_for_import",
                progress_task=self._import_task,
            )

        try:
            await self._import_task
        except TimeoutError:
            return self.async_show_progress_done(next_step_id="magic_import_timeout")
        finally:
            self._import_task = None
        return self.async_show_progress_done(next_step_id="magic_discover")

    async def async_step_magic_import_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow retrying an expired Magic import."""
        if self._timeout_shown and user_input is not None:
            self._new_magic_session()
            return await self.async_step_magic_family()
        self._timeout_shown = True
        return self.async_show_form(step_id="magic_import_timeout")

    async def async_step_magic_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare an imported Magic family for confirmation."""
        assert self._session is not None
        families = self._session.families
        if not families:
            return self.async_abort(reason="invalid_import")
        if len(families) != 1:
            return self.async_abort(reason="multiple_families")

        family = families[0]
        if not family.gateways:
            return self.async_abort(reason="no_gateway")
        unique_id = f"magic:{family.family_id}"
        self._existing_entry = next(
            (
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.unique_id == unique_id
            ),
            None,
        )
        # The latest scan wins; HA aborts the other flows when this one finishes.
        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        if self._existing_entry is None:
            self._abort_if_unique_id_configured()
        imported_macs = {gateway.mac.lower() for gateway in family.gateways}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == unique_id or not is_magic_entry(entry):
                continue
            if imported_macs & {
                gateway.mac.lower()
                for gateway in gateways_from_entry_data(dict(entry.data))
            }:
                return self.async_abort(
                    reason="gateway_in_other_family",
                    description_placeholders={"family": entry.title},
                )
        self._family = family
        self._gateways = [
            DiscoveredRMMax(
                host="",
                mac=gateway.mac,
                devtype=gateway.devtype or RM_MAX_DEVTYPE,
                name=gateway.name,
                port=0,
            )
            for gateway in family.gateways
        ]
        self.context["title_placeholders"] = {"name": family.name}
        return await self.async_step_magic_confirm()

    async def async_step_magic_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm or reimport the Magic family."""
        assert self._family is not None
        assert self._gateways is not None
        if user_input is not None:
            data = family_to_entry_data(self._family, self._gateways)
            data[CONF_ENTRY_KIND] = ENTRY_KIND_MAGIC_FAMILY
            if self._existing_entry is not None:
                return self.async_update_reload_and_abort(
                    self._existing_entry,
                    data=data,
                    title=self._family.name,
                    reason="reconfigure_successful",
                )
            return self.async_create_entry(title=self._family.name, data=data)
        return self.async_show_form(
            step_id="magic_confirm",
            description_placeholders={
                "family_name": self._family.name,
                "gateway_count": str(len(self._gateways)),
                "device_count": str(len(self._family.devices)),
            },
        )
