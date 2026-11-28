"""The config flow for APsystems local API integration."""

from typing import Any, override

from aiohttp.client_exceptions import ClientConnectionError
from APsystemsEZ1 import APsystemsEZ1M
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVICE_TYPE,
    DEFAULT_PORT,
    DEVICE_TYPE_EZ1,
    DEVICE_TYPE_LAKE6,
    DOMAIN,
)
from .lake6.client import Lake6ApiClient, Lake6ApiError
from .lake6.const import LAKE6_DEFAULT_PORT

DEVICE_TYPE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[DEVICE_TYPE_EZ1, DEVICE_TYPE_LAKE6],
        translation_key="device_type",
        mode=selector.SelectSelectorMode.LIST,
    )
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_DEVICE_TYPE, default=DEVICE_TYPE_EZ1
        ): DEVICE_TYPE_SELECTOR,
        probatio.Required(CONF_IP_ADDRESS): cv.string,
        probatio.Optional(CONF_PORT): probatio.Port(),
    }
)


class APsystemsLocalAPIFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Apsystems local."""

    # Adding `device_type` is a minor bump: a major bump would make an older
    # Home Assistant refuse the entry after a downgrade. Version 1 entries are
    # EZ1 and are backfilled by `async_migrate_entry`.
    VERSION = 1
    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            probed = await self._async_probe(user_input)
            if probed is None:
                errors["base"] = "cannot_connect"
            else:
                unique_id, title = probed
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_probe(self, user_input: dict[str, Any]) -> tuple[str, str] | None:
        """Return (unique_id, entry title), or None when unreachable.

        A missing `device_type` predates Lake support and means EZ1 (§1).
        """
        if user_input.get(CONF_DEVICE_TYPE, DEVICE_TYPE_EZ1) == DEVICE_TYPE_LAKE6:
            return await self._async_probe_lake6(user_input)
        return await self._async_probe_ez1(user_input)

    async def _async_probe_ez1(
        self, user_input: dict[str, Any]
    ) -> tuple[str, str] | None:
        """Identify an EZ1 inverter."""
        api = APsystemsEZ1M(
            ip_address=user_input[CONF_IP_ADDRESS],
            port=user_input.get(CONF_PORT, DEFAULT_PORT),
            session=async_get_clientsession(self.hass, False),
        )
        try:
            device_info = await api.get_device_info()
        except TimeoutError, ClientConnectionError:
            return None
        # Keep the historical EZ1 title so existing and new entries read the same.
        return device_info.deviceId, "Solar"

    async def _async_probe_lake6(
        self, user_input: dict[str, Any]
    ) -> tuple[str, str] | None:
        """Identify a Lake series unit."""
        client = Lake6ApiClient(
            host=user_input[CONF_IP_ADDRESS],
            session=async_get_clientsession(self.hass, False),
            port=user_input.get(CONF_PORT, LAKE6_DEFAULT_PORT),
        )
        try:
            device = await client.async_get_device()
        except Lake6ApiError:
            return None
        # The reported type is the model, so the title matches the device page.
        return device.dev_id, device.device_type
