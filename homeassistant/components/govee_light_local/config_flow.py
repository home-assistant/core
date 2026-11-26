"""Config flow for Govee light local."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, override

from govee_local_api import GoveeDevice
import probatio

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util.network import is_ipv4_address

from .const import CONF_FINGERPRINT, DOMAIN
from .coordinator import (
    NoListeningAddressesError,
    async_acquire_coordinator,
    async_release_coordinator,
    is_legacy_entry,
)

_LOGGER = logging.getLogger(__name__)


async def _async_discover_devices(hass: HomeAssistant) -> bool:
    """Offer the lamps answering a scan; return if any is offered or was set up."""

    # A second controller would take replies away from the one the set up
    # entries share, so the scan goes through that one.
    try:
        coordinator = await async_acquire_coordinator(hass)
    except NoListeningAddressesError:
        _LOGGER.debug("No enabled IPv4 addresses to listen on")
        return False
    except OSError as ex:
        _LOGGER.error("Start failed, errno: %d", ex.errno)
        return False

    try:
        return coordinator.async_offer_devices(await coordinator.async_scan())
    finally:
        await async_release_coordinator(hass, coordinator)


async def _async_probe_device(
    hass: HomeAssistant, ip_address: str
) -> GoveeDevice | None:
    """Return the lamp answering at the address, if any."""
    try:
        coordinator = await async_acquire_coordinator(hass)
    except NoListeningAddressesError, OSError:
        return None
    try:
        return await coordinator.async_probe(ip_address)
    finally:
        await async_release_coordinator(hass, coordinator)


class GoveeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee light local."""

    VERSION = 2

    _ip_address: str
    _model: str
    _scan_task: asyncio.Task[bool] | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user search the network or enter the address of a lamp."""
        return self.async_show_menu(step_id="user", menu_options=["scan", "manual"])

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan for lamps; each one found is offered as a discovered device."""
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(
                _async_discover_devices(self.hass)
            )
        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="scan", progress_action="scan", progress_task=self._scan_task
            )
        return self.async_show_progress_done(next_step_id="scan_done")

    async def async_step_scan_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Tell the user whether the scan found any lamp."""
        if TYPE_CHECKING:
            assert self._scan_task is not None
        if not self._scan_task.result():
            return self.async_abort(reason="no_devices_found")
        return self.async_abort(reason="discovery_started")

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add the lamp at an address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ip_address = user_input[CONF_IP_ADDRESS]
            if not is_ipv4_address(ip_address):
                errors[CONF_IP_ADDRESS] = "invalid_host"
            elif (device := await _async_probe_device(self.hass, ip_address)) is None:
                errors[CONF_IP_ADDRESS] = "cannot_connect"
            else:
                # A discovery flow for the lamp does not hold back the user.
                await self.async_set_unique_id(
                    device.fingerprint, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(
                    updates={CONF_IP_ADDRESS: ip_address}
                )
                return self.async_create_entry(
                    title=device.sku, data={CONF_IP_ADDRESS: ip_address}
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required(CONF_IP_ADDRESS): str}), user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of a lamp."""
        entry = self._get_reconfigure_entry()
        if is_legacy_entry(entry):
            # It has no lamp of its own until one of its lamps answers a scan.
            return self.async_abort(reason="not_split")
        errors: dict[str, str] = {}
        if user_input is not None:
            ip_address = user_input[CONF_IP_ADDRESS]
            if not is_ipv4_address(ip_address):
                errors[CONF_IP_ADDRESS] = "invalid_host"
            elif (device := await _async_probe_device(self.hass, ip_address)) is None:
                errors[CONF_IP_ADDRESS] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    device.fingerprint, raise_on_progress=False
                )
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_IP_ADDRESS: ip_address}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required(CONF_IP_ADDRESS): str}),
                user_input or entry.data,
            ),
            errors=errors,
        )

    @override
    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle a lamp that answered the shared controller's scan."""
        await self._async_set_unique_id(discovery_info)
        self._ip_address = discovery_info[CONF_IP_ADDRESS]
        self._model = discovery_info[CONF_MODEL]
        return await self.async_step_discovery_confirm()

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Add a lamp that the entry for every lamp had already set up."""
        await self._async_set_unique_id(import_data)
        # The address is not known for a lamp that has not answered yet.
        return self.async_create_entry(
            title=import_data[CONF_MODEL],
            data={CONF_IP_ADDRESS: import_data[CONF_IP_ADDRESS]},
        )

    async def _async_set_unique_id(self, discovery_info: dict[str, Any]) -> None:
        """Identify the lamp, storing a new address if it is already configured."""
        await self.async_set_unique_id(discovery_info[CONF_FINGERPRINT])
        if (ip_address := discovery_info[CONF_IP_ADDRESS]) is not None:
            self._abort_if_unique_id_configured(updates={CONF_IP_ADDRESS: ip_address})
        else:
            self._abort_if_unique_id_configured()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            # The lamp can have got its entry while the form was open.
            self._abort_if_unique_id_configured(
                updates={CONF_IP_ADDRESS: self._ip_address}
            )
            return self.async_create_entry(
                title=self._model, data={CONF_IP_ADDRESS: self._ip_address}
            )

        placeholders = {"model": self._model, "ip": self._ip_address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )
