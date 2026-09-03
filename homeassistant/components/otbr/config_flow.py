"""Config flow for the Open Thread Border Router integration."""

from contextlib import suppress
import logging
from typing import TYPE_CHECKING, cast, override

import aiohttp
import python_otbr_api
from python_otbr_api import tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType
import voluptuous as vol
import yarl

from homeassistant.components.hassio import AddonError, AddonManager
from homeassistant.components.homeassistant_yellow import hardware as yellow_hardware
from homeassistant.components.thread import async_get_preferred_dataset
from homeassistant.config_entries import (
    SOURCE_HASSIO,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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

    if device and "Nabu_Casa_ZBT-2" in device:
        return f"Home Assistant Connect ZBT-2 ({discovery_info.name})"

    return discovery_info.name


class OTBRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Thread Border Router."""

    VERSION = 1

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
                        channel=allowed_channel or DEFAULT_CHANNEL,
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
        border_agent_id = await api.get_border_agent_id()
        _LOGGER.debug("border agent id for url %s: %s", otbr_url, border_agent_id.hex())

        if await self._is_border_agent_id_configured(border_agent_id):
            raise AlreadyConfigured

        await self._set_dataset(api, otbr_url)

        return border_agent_id

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Set up by user."""
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
            step_id="user", data_schema=data_schema, errors=errors
        )

    @callback
    def _async_find_legacy_entry_by_host(self, host: str) -> ConfigEntry | None:
        """Return an entry created by the first version of the integration.

        Those entries have no unique id, they can only be matched by host.
        This can be removed in HA Core 2027.3.
        """
        for entry in self._async_current_entries():
            if (
                entry.source == SOURCE_HASSIO
                and entry.unique_id is None
                and yarl.URL(entry.data["url"]).host == host
            ):
                return entry
        return None

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle hassio discovery."""
        config = discovery_info.config
        url = f"http://{config['host']}:{config['port']}"
        config_entry_data = {"url": url}

        matching_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, discovery_info.uuid
        )
        if matching_entry is None:
            # Entries created by the first version of the integration have no unique
            # id and can only be matched to this discovery by host
            # This fallback can be removed in HA Core 2027.3
            matching_entry = self._async_find_legacy_entry_by_host(config["host"])

        if matching_entry is not None:
            # Update the URL in case the add-on moved, and set the unique id of
            # entries created by the first version
            # Remove the unique_id update in HA Core 2027.3
            updated = self.hass.config_entries.async_update_entry(
                matching_entry,
                data=config_entry_data,
                unique_id=discovery_info.uuid,
            )
            if matching_entry.state is ConfigEntryState.SETUP_RETRY:
                # The discovery means the add-on is back, don't wait for the
                # setup retry backoff to expire
                self.hass.config_entries.async_schedule_reload(matching_entry.entry_id)
            elif not updated and matching_entry.state is ConfigEntryState.LOADED:
                # Reload the entry since OTBR has restarted, an entry which was
                # updated is reloaded by its update listener
                await self.hass.config_entries.async_reload(matching_entry.entry_id)

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
