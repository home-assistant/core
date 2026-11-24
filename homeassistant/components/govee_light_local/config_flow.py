"""Config flow for Govee light local."""

import logging
from typing import Any, override

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_FINGERPRINT, DOMAIN
from .coordinator import (
    NoListeningAddressesError,
    async_acquire_coordinator,
    async_release_coordinator,
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


class GoveeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee light local."""

    VERSION = 2

    _ip_address: str
    _model: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan for lamps; each one found is offered as a discovered device."""
        if not await _async_discover_devices(self.hass):
            return self.async_abort(reason="no_devices_found")
        return self.async_abort(reason="discovery_started")

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
            return self.async_create_entry(
                title=self._model, data={CONF_IP_ADDRESS: self._ip_address}
            )

        placeholders = {"model": self._model, "ip": self._ip_address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )
