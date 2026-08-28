"""Options flow for the BLUETTI integration.

Lets the user add devices bound to their BLUETTI account after the initial
setup, without going through the OAuth2 login flow again (the stored token
is reused), and lets the user configure an optional local Modbus connection
for any enabled device that supports it (Balco260, EP2000).
"""

import logging
from typing import Any

from bluetti_modbus_lib import get_device
from modbus_connection import ModbusTcpParams
from modbus_connection.exceptions import ModbusError
from pybluetti import ProductClient, UnifyResponse, UserProduct
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import EVENT_TOKEN_EXPIRED
from .modbus_support import modbus_dev_type_for_model
from .profile.application_profile import APPLICATION_PROFILE

__LOGGER__ = logging.getLogger(__name__)


def _parse_products(entry: ConfigEntry) -> list[UserProduct]:
    return [
        UserProduct.model_validate(p) if isinstance(p, dict) else p
        for p in entry.data.get("products", [])
    ]


class BluettiOptionsFlowHandler(OptionsFlow):
    """Handle an options flow to add/configure BLUETTI devices on an existing entry."""

    _product_client: ProductClient
    _products: list[UserProduct]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Route to the add-devices form, or a menu if local Modbus is also configurable."""
        entry: ConfigEntry = self.config_entry
        enabled_devices = set(entry.options.get("devices", []))
        modbus_capable = [
            product
            for product in _parse_products(entry)
            if product.sn in enabled_devices
            and modbus_dev_type_for_model(product.model)
        ]

        if not modbus_capable:
            return await self.async_step_add_devices(user_input)

        return self.async_show_menu(
            step_id="init", menu_options=["add_devices", "configure_modbus"]
        )

    async def async_step_add_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick additional devices from their BLUETTI account."""
        entry: ConfigEntry = self.config_entry

        if user_input is not None:
            selected = user_input["devices"]
            try:
                result = await self._product_client.bind_devices(
                    {"bindSnList": selected}
                )
            except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", err)
                return self.async_abort(reason="cannot_connect")

            # bind_devices() returns a plain str for a non-JSON server
            # response, and a nonzero msgCode without raising - either way
            # the devices were not actually bound, so this must not fall
            # through and persist them as though it succeeded.
            if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
                __LOGGER__.error("Failed to bind BLUETTI devices: %s", result)
                return self.async_abort(reason="cannot_connect")

            current_devices = entry.options.get("devices", [])
            merged_devices = list(set(current_devices) | set(selected))

            existing_products = entry.data.get("products", [])
            existing_sns = {
                p.get("sn") if isinstance(p, dict) else p.sn for p in existing_products
            }
            new_products = [p for p in self._products if p.sn not in existing_sns]
            merged_products = existing_products + [p.model_dump() for p in new_products]

            # async_create_entry's data REPLACES entry.options wholesale (see
            # OptionsFlowManager.async_finish_flow) - carry the existing
            # "modbus" key forward explicitly, or configuring a device's
            # local Modbus connection would get silently wiped the next
            # time more devices are added here.
            merged_options = {
                "devices": merged_devices,
                "modbus": entry.options.get("modbus", {}),
            }

            # A single upfront async_update_entry() call for both the new
            # products (data) and the new device list (options) - entry
            # already has _async_update_listener registered, which reloads
            # it on any change. Returning async_create_entry(data=...)
            # below still makes OptionsFlowManager perform its own
            # async_update_entry(entry, options=...) call afterward (that's
            # the only sanctioned way to persist an options flow's result) -
            # applying the exact same merged_options here first means that
            # second call finds entry.options already equal and is a
            # genuine no-op (ConfigEntries._async_update_entry only fires
            # listeners/reloads when something actually differs), instead
            # of reloading the entry a second time for one "add devices"
            # action.
            self.hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, "products": merged_products},
                options=merged_options,
            )

            return self.async_create_entry(data=merged_options)

        # ApplicationProfile is a module-level singleton populated by
        # config_flow.py's async_step_user - relying on that having already
        # run in this process is a real cross-test hazard under pytest-xdist
        # (each test file can get its own fresh worker process), so this
        # flow (entered without going through async_step_user again) must
        # load it itself too. Idempotent: re-reads the same static file.
        await APPLICATION_PROFILE.load_config(self.hass)

        http_session = async_get_clientsession(self.hass)
        try:
            # Reading entry.data["token"] directly would skip Home
            # Assistant's refresh path - an options flow opened after the
            # stored access token has expired (but the refresh token is
            # still valid) would otherwise fail as cannot_connect for no
            # real reason. Same OAuth2Session-backed refresh path setup
            # uses in __init__.py.
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    self.hass, entry
                )
            )
            oauth_session = config_entry_oauth2_flow.OAuth2Session(
                self.hass, entry, implementation
            )
            await oauth_session.async_ensure_token_valid()
            access_token = oauth_session.token["access_token"]
            product_client = ProductClient(
                http_session,
                APPLICATION_PROFILE.config["server"]["gateway"],
                access_token,
                on_auth_expired=lambda: self.hass.bus.fire(EVENT_TOKEN_EXPIRED),
            )
            products = await product_client.get_user_products()
        except Exception as err:  # noqa: BLE001 - cloud SDK call at a system boundary; any failure aborts the flow
            __LOGGER__.error("Failed to fetch BLUETTI products: %s", err)
            return self.async_abort(reason="cannot_connect")

        # Checked before iterating products.data below: it's `T | None` on
        # the wire, and a cloud response that omits "data" entirely would
        # otherwise crash the dict comprehension with an unhandled
        # TypeError instead of aborting gracefully.
        if not products.data:
            return self.async_abort(reason="no_devices_available")

        self._product_client = product_client
        self._products = products.data

        enabled_devices = set(entry.options.get("devices", []))
        available_devices = {
            product.sn: f"{product.name} - {product.sn}"
            for product in products.data
            if product.sn not in enabled_devices
        }

        if not available_devices:
            return self.async_abort(reason="all_devices_exists")

        schema = vol.Schema(
            {
                vol.Required(
                    "devices",
                    default=list(available_devices.keys()),
                ): cv.multi_select(available_devices)
            }
        )

        return self.async_show_form(step_id="add_devices", data_schema=schema)

    async def async_step_configure_modbus(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user configure an optional local Modbus connection for one device."""
        entry: ConfigEntry = self.config_entry
        enabled_devices = set(entry.options.get("devices", []))
        modbus_capable = {
            product.sn: product
            for product in _parse_products(entry)
            if product.sn in enabled_devices
            and modbus_dev_type_for_model(product.model)
        }

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            sn = user_input["device_sn"]
            host = user_input["host"]
            port = user_input["port"]
            dev_type = modbus_dev_type_for_model(modbus_capable[sn].model)
            assert dev_type is not None, (
                "device_sn is only offered from modbus_capable, which is already filtered by dev_type"
            )

            try:
                # A one-off connectivity check, not a persistent connection -
                # async_get_temporary_unit shares a connection already held by
                # a config entry (e.g. re-testing a device that's already
                # configured) and closes what it opens itself, same as the
                # coordinator's async_get_unit does for entry-lifetime holds.
                async with async_get_temporary_unit(
                    self.hass, ModbusTcpParams(host=host, port=port), 1
                ) as unit:
                    device = get_device(dev_type, unit)
                    assert device is not None, (
                        "dev_type comes from modbus_dev_type_for_model, which"
                        " only returns types get_device recognizes"
                    )
                    await device.async_update()
            except (ModbusError, TimeoutError, HomeAssistantError) as err:
                errors["base"] = "cannot_connect"
                description_placeholders["error"] = str(err)

            if not errors:
                modbus_options = {
                    **entry.options.get("modbus", {}),
                    sn: {"host": host, "port": port},
                }
                # async_create_entry's data REPLACES entry.options wholesale
                # (see OptionsFlowManager.async_finish_flow) - a bare
                # async_update_entry() call here, followed by
                # async_create_entry(data={}), would have the second call
                # immediately wipe out what the first one just set (including
                # "devices"). Pass the full merged options as this single
                # call's data instead.
                return self.async_create_entry(
                    data={**entry.options, "modbus": modbus_options}
                )

        # Pre-fill with whatever the user just typed (re-showing the form
        # after a failed connectivity check), else the currently saved
        # connection for the default (first) device - reopening this step
        # to tweak an existing connection should not start from blank.
        default_sn = (user_input or {}).get("device_sn") or next(
            iter(modbus_capable), None
        )
        existing = (
            entry.options.get("modbus", {}).get(default_sn, {}) if default_sn else {}
        )
        default_host = (user_input or {}).get("host", existing.get("host", ""))
        default_port = (user_input or {}).get("port", existing.get("port", 502))

        schema = vol.Schema(
            {
                vol.Required("device_sn", default=default_sn): vol.In(
                    {
                        sn: f"{product.name} ({sn})"
                        for sn, product in modbus_capable.items()
                    }
                ),
                vol.Required("host", default=default_host): TextSelector(),
                vol.Required("port", default=default_port): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.BOX, min=1, max=65535
                        )
                    ),
                    vol.Coerce(int),
                ),
            }
        )

        return self.async_show_form(
            step_id="configure_modbus",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
