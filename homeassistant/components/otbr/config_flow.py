"""Config flow for the Open Thread Border Router integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from aiohttp.client_exceptions import ClientConnectorError
import python_otbr_api
from python_otbr_api import tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType
import voluptuous as vol
import yarl

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.components.homeassistant_hardware.util import get_otbr_addon_manager
from homeassistant.components.homeassistant_yellow import hardware as yellow_hardware
from homeassistant.components.thread import async_get_preferred_dataset
from homeassistant.components.usb import async_get_usb_ports
from homeassistant.config_entries import (
    SOURCE_HASSIO,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import DEFAULT_CHANNEL, DOMAIN
from .util import (
    compose_default_network_name,
    generate_random_pan_id,
    get_allowed_channel,
)

if TYPE_CHECKING:
    from . import OTBRConfigEntry

_LOGGER = logging.getLogger(__name__)


CONF_DEVICE = "device"

# Timeout and retry constants for OTBR connection
OTBR_CONNECTION_TIMEOUT = 10.0
OTBR_RETRY_BACKOFF = 0.5


class AlreadyConfigured(HomeAssistantError):
    """Raised when the router is already configured."""


@callback
def get_addon_manager(hass: HomeAssistant, slug: str) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass, _LOGGER, "OpenThread Border Router", slug)


def _is_yellow(hass: HomeAssistant) -> bool:
    """Return True if Home Assistant is running on a Home Assistant Yellow."""
    try:
        yellow_hardware.async_info(hass)
    except HomeAssistantError:
        return False
    return True


async def _title(hass: HomeAssistant, discovery_info: HassioServiceInfo) -> str:
    """Return config entry title."""
    device: str | None = None
    addon_manager = get_addon_manager(hass, discovery_info.slug)

    with suppress(AddonError):
        addon_info = await addon_manager.async_get_addon_info()
        device = addon_info.options.get("device")

    if _is_yellow(hass) and device == "/dev/ttyAMA1":
        return f"Home Assistant Yellow ({discovery_info.name})"

    if device and ("Connect_ZBT-1" in device or "SkyConnect" in device):
        return f"Home Assistant Connect ZBT-1 ({discovery_info.name})"

    return discovery_info.name


class OTBRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Thread Border Router."""

    VERSION = 1

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate otbr config flow."""
        super().__init__(*args, **kwargs)

        self._device: str | None = None
        self._url: str | None = None  # used only in recommended setup

        self.addon_install_task: asyncio.Task | None = None
        self.addon_start_task: asyncio.Task | None = None
        self.addon_connect_task: asyncio.Task | None = None

    async def _set_dataset(self, api: python_otbr_api.OTBR, otbr_url: str) -> None:
        """Connect to the OTBR and create or apply a dataset if it doesn't have one."""
        if await api.get_active_dataset_tlvs() is None:
            allowed_channel = await get_allowed_channel(self.hass, otbr_url)

            thread_dataset_channel = None
            thread_dataset_tlv = await async_get_preferred_dataset(self.hass)
            if thread_dataset_tlv:
                dataset = tlv_parser.parse_tlv(thread_dataset_tlv)
                if channel := dataset.get(MeshcopTLVType.CHANNEL):
                    thread_dataset_channel = cast(tlv_parser.Channel, channel).channel

            if thread_dataset_tlv is not None and (
                not allowed_channel or allowed_channel == thread_dataset_channel
            ):
                await api.set_active_dataset_tlvs(bytes.fromhex(thread_dataset_tlv))
            else:
                _LOGGER.debug(
                    "not importing TLV with channel %s for %s",
                    thread_dataset_channel,
                    otbr_url,
                )
                pan_id = generate_random_pan_id()
                await api.create_active_dataset(
                    python_otbr_api.ActiveDataSet(
                        channel=allowed_channel if allowed_channel else DEFAULT_CHANNEL,
                        network_name=compose_default_network_name(pan_id),
                        pan_id=pan_id,
                    )
                )
            await api.set_enabled(True)

    async def _is_border_agent_id_configured(self, border_agent_id: bytes) -> bool:
        """Return True if another config entry's OTBR has the same border agent id."""
        config_entry: OTBRConfigEntry
        for config_entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            data = config_entry.runtime_data
            try:
                other_border_agent_id = await data.get_border_agent_id()
            except HomeAssistantError:
                _LOGGER.debug(
                    "Could not read border agent id from %s", data.url, exc_info=True
                )
                continue
            _LOGGER.debug(
                "border agent id for existing url %s: %s",
                data.url,
                other_border_agent_id.hex(),
            )
            if border_agent_id == other_border_agent_id:
                return True
        return False

    async def _connect_and_configure_router(self, otbr_url: str) -> bytes:
        """Connect to the router and configure it if needed.

        Will raise if the router's border agent id is in use by another config entry.
        Returns the router's border agent id.
        """
        api = python_otbr_api.OTBR(otbr_url, async_get_clientsession(self.hass), 10)
        border_agent_id: bytes = await api.get_border_agent_id()
        _LOGGER.debug("border agent id for url %s: %s", otbr_url, border_agent_id.hex())

        if await self._is_border_agent_id_configured(border_agent_id):
            raise AlreadyConfigured

        await self._set_dataset(api, otbr_url)

        return border_agent_id

    async def _connect_with_retry(self, url: str) -> bytes:
        """Connect to OTBR with retry logic for up to 10 seconds."""
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed_time = asyncio.get_event_loop().time() - start_time

            if elapsed_time >= OTBR_CONNECTION_TIMEOUT:
                _LOGGER.warning(
                    "Failed to connect to OTBR@%s after %.1f seconds",
                    url,
                    OTBR_CONNECTION_TIMEOUT,
                )
                raise HomeAssistantError(
                    f"Failed to connect to OTBR after {OTBR_CONNECTION_TIMEOUT} seconds"
                )

            try:
                return await self._connect_and_configure_router(url)
            except ClientConnectorError as exc:
                _LOGGER.debug(
                    "ClientConnectorError after %.2f seconds, retrying in %.1fs: %s",
                    elapsed_time,
                    OTBR_RETRY_BACKOFF,
                    exc,
                )
                await asyncio.sleep(OTBR_RETRY_BACKOFF)

    async def _async_get_addon_info(self, addon_manager: AddonManager) -> AddonInfo:
        """Return add-on info."""
        try:
            addon_info = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_info_failed",
                description_placeholders={
                    "addon_name": addon_manager.addon_name,
                },
            ) from err

        return addon_info

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Set up by user."""
        if not is_hassio(self.hass):
            # skip to url step if not hassio
            return await self.async_step_url()

        return self.async_show_menu(
            step_id="user",
            menu_options=["recommended", "url"],
        )

    async def async_step_recommended(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Select usb device."""
        if self._device:
            # device already set, skip to addon step
            return await self.async_step_addon()

        if user_input is not None and (
            usb_path := user_input.get(CONF_DEVICE, "").strip()
        ):
            self._device = usb_path
            return await self.async_step_addon()

        try:
            ports = await async_get_usb_ports(self.hass)
        except OSError as err:
            _LOGGER.error("Failed to get USB ports: %s", err)
            return self.async_abort(reason="usb_ports_failed")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE): vol.In(ports),
            }
        )
        return self.async_show_form(step_id="recommended", data_schema=data_schema)

    async def async_step_addon(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Set up the addon."""
        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_install_otbr_addon()

        if addon_info.state == AddonState.RUNNING:
            await otbr_manager.async_stop_addon()

        return await self.async_step_start_otbr_addon()

    async def async_step_install_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress dialog for installing the OTBR addon."""
        addon_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)

        _LOGGER.debug("OTBR addon info: %s", addon_info)

        if not self.addon_install_task:
            self.addon_install_task = self.hass.async_create_task(
                addon_manager.async_install_addon_waiting(),
                "OTBR addon install",
            )

        if not self.addon_install_task.done():
            return self.async_show_progress(
                step_id="install_otbr_addon",
                progress_action="install_otbr_addon",
                description_placeholders={
                    "addon_name": addon_manager.addon_name,
                },
                progress_task=self.addon_install_task,
            )

        try:
            await self.addon_install_task
        except AddonError as err:
            _LOGGER.error(err)
            return self.async_abort(
                reason="addon_install_failed",
                description_placeholders={
                    "addon_name": addon_manager.addon_name,
                },
            )
        finally:
            self.addon_install_task = None

        return self.async_show_progress_done(next_step_id="addon")

    async def async_step_start_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure OTBR to point to the SkyConnect and run the addon."""
        otbr_manager = get_otbr_addon_manager(self.hass)

        if not self.addon_start_task:
            addon_info = await self._async_get_addon_info(otbr_manager)

            assert self._device is not None
            new_addon_config = {
                **addon_info.options,
                "device": self._device,
                "autoflash_firmware": False,
            }

            _LOGGER.debug("Reconfiguring OTBR addon with %s", new_addon_config)

            try:
                await otbr_manager.async_set_addon_options(new_addon_config)
            except AddonError as err:
                _LOGGER.error(err)
                raise AbortFlow(
                    "addon_set_config_failed",
                    description_placeholders={
                        "addon_name": otbr_manager.addon_name,
                    },
                ) from err

            self.addon_start_task = self.hass.async_create_task(
                otbr_manager.async_start_addon_waiting()
            )

        if not self.addon_start_task.done():
            return self.async_show_progress(
                step_id="start_otbr_addon",
                progress_action="start_otbr_addon",
                description_placeholders={
                    "addon_name": otbr_manager.addon_name,
                },
                progress_task=self.addon_start_task,
            )

        try:
            await self.addon_start_task
        except (AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            return self.async_abort(
                reason="addon_start_failed",
                description_placeholders={
                    "addon_name": otbr_manager.addon_name,
                },
            )
        finally:
            self.addon_start_task = None

        return self.async_show_progress_done(next_step_id="connect_otbr")

    async def async_step_connect_otbr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect to OTBR with retry logic."""
        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)
        self._url = f"http://{addon_info.hostname}:8081"

        if not self.addon_connect_task:
            self.addon_connect_task = self.hass.async_create_task(
                self._connect_with_retry(self._url)
            )

        if not self.addon_connect_task.done():
            return self.async_show_progress(
                step_id="connect_otbr",
                progress_action="connect_otbr",
                description_placeholders={
                    "addon_name": otbr_manager.addon_name,
                },
                progress_task=self.addon_connect_task,
            )

        try:
            border_agent_id = await self.addon_connect_task
        except AlreadyConfigured:
            return self.async_abort(reason="already_configured")
        except (
            python_otbr_api.OTBRError,
            aiohttp.ClientError,
            TimeoutError,
            HomeAssistantError,
        ) as exc:
            _LOGGER.warning("Failed to communicate with OTBR@%s: %s", self._url, exc)
            return self.async_abort(reason="unknown")
        finally:
            self.addon_connect_task = None

        await self.async_set_unique_id(border_agent_id.hex())
        return self.async_show_progress_done(next_step_id="addon_done")

    async def async_step_addon_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on done."""
        config_entry_data = {"url": self._url, "device": self._device}
        return self.async_create_entry(
            title="Open Thread Border Router",
            data=config_entry_data,
        )

    async def async_step_url(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Custom step to set up by URL."""
        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            try:
                border_agent_id = await self._connect_and_configure_router(url)
            except AlreadyConfigured:
                errors["base"] = "already_configured"
            except (
                python_otbr_api.OTBRError,
                aiohttp.ClientError,
                TimeoutError,
            ) as exc:
                _LOGGER.debug("Failed to communicate with OTBR@%s: %s", url, exc)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(border_agent_id.hex())
                return self.async_create_entry(
                    title="Open Thread Border Router",
                    data={CONF_URL: url},
                )

        data_schema = vol.Schema({CONF_URL: str})
        return self.async_show_form(
            step_id="url", data_schema=data_schema, errors=errors
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle hassio discovery."""
        config = discovery_info.config
        url = f"http://{config['host']}:{config['port']}"
        config_entry_data = {"url": url}

        if current_entries := self._async_current_entries():
            for current_entry in current_entries:
                if current_entry.source != SOURCE_HASSIO:
                    continue
                current_url = yarl.URL(current_entry.data["url"])
                if not (unique_id := current_entry.unique_id):
                    # The first version did not set a unique_id
                    # so if the entry does not have a unique_id
                    # we have to assume it's the first version
                    # This check can be removed in HA Core 2025.9
                    unique_id = discovery_info.uuid

                if unique_id != discovery_info.uuid:
                    continue

                if (
                    current_url.host != config["host"]
                    or current_url.port == config["port"]
                ):
                    # Reload the entry since OTBR has restarted
                    if current_entry.state == ConfigEntryState.LOADED:
                        assert current_entry.unique_id is not None
                        await self.hass.config_entries.async_reload(
                            current_entry.entry_id
                        )

                    continue

                # Update URL with the new port
                self.hass.config_entries.async_update_entry(
                    current_entry,
                    data=config_entry_data,
                    unique_id=unique_id,  # Remove in HA Core 2025.9
                )
                return self.async_abort(reason="already_configured")

        try:
            await self._connect_and_configure_router(url)
        except AlreadyConfigured:
            return self.async_abort(reason="already_configured")
        except (
            python_otbr_api.OTBRError,
            aiohttp.ClientError,
            TimeoutError,
        ) as exc:
            _LOGGER.warning("Failed to communicate with OTBR@%s: %s", url, exc)
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(discovery_info.uuid)
        return self.async_create_entry(
            title=await _title(self.hass, discovery_info),
            data=config_entry_data,
        )
