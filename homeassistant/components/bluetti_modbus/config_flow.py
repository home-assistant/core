"""Config flow to configure the BLUETTI Modbus integration."""

import logging
from typing import TYPE_CHECKING, Any, override

from modbus_connection import ModbusError, ModbusTcpParams
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import SOURCE_IGNORE, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_UNIT_ID, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN, MODEL, MODEL_ID
from .device import restricted_device

_LOGGER = logging.getLogger(__name__)

STEP_USER = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=247, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(int),
        ),
    }
)


class BluettiModbusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BLUETTI Modbus config flow."""

    VERSION = 1

    _discovered: dict[str, Any]

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask where the device is, then probe it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # A link some entry already owns is rejected before the device is
            # probed, so a duplicate aborts even while the device is offline.
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                }
            )
            errors, serial = await self._async_validate(user_input)
            if not errors:
                if TYPE_CHECKING:
                    assert serial is not None
                # Catches the same device already added under a different
                # link (moved to a new address, for example). A pending
                # discovery of it is replaced rather than blocking this setup.
                await self.async_set_unique_id(serial, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=MODEL, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a power station announcing itself over mDNS."""
        host = discovery_info.host
        # The device accepts few Modbus clients at once, so a known one is
        # dropped before it is asked anything.
        self._async_abort_entries_match({CONF_HOST: host})

        data = {
            CONF_HOST: host,
            CONF_PORT: DEFAULT_PORT,
            CONF_UNIT_ID: DEFAULT_UNIT_ID,
        }
        errors, serial = await self._async_validate(data)
        if errors:
            return self.async_abort(reason=errors["base"])
        if TYPE_CHECKING:
            assert serial is not None

        await self.async_set_unique_id(serial)
        if entry := self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, serial
        ):
            # Only the host is updated, so only an entry on the port and device
            # ID the probe just used can follow its power station.
            if entry.source == SOURCE_IGNORE or any(
                entry.data[key] != data[key] for key in (CONF_PORT, CONF_UNIT_ID)
            ):
                return self.async_abort(reason="already_configured")
            # Same power station at a new address.
            return self.async_update_reload_and_abort(
                entry, data_updates={CONF_HOST: host}, reason="already_configured"
            )

        self._discovered = data
        self.context["title_placeholders"] = {"name": MODEL, "host": host}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setting up a discovered power station."""
        if user_input is not None:
            return self.async_create_entry(title=MODEL, data=self._discovered)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": MODEL,
                "host": self._discovered[CONF_HOST],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at the address the device moved to."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, serial = await self._async_validate(user_input)
            if not errors:
                if TYPE_CHECKING:
                    assert serial is not None
                await self.async_set_unique_id(serial)
                # Another serial is a different power station, not a moved one.
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], str | None]:
        """Probe the device, returning form errors and its serial number.

        The serial number is ``None`` only alongside a non-empty errors
        dict - a successful probe always confirms one.
        """
        params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
        try:
            async with async_get_temporary_unit(
                self.hass, params, data[CONF_UNIT_ID]
            ) as unit:
                device = restricted_device(unit)
                await device.async_update_with_retry()
        except HomeAssistantError:
            # Claimed by another entry with link settings one shared connection
            # cannot honour; retrying won't help.
            return {"base": "link_settings_in_use"}, None
        except ModbusError:
            return {"base": "cannot_connect"}, None
        except Exception:
            _LOGGER.exception("Unexpected exception while probing the device")
            return {"base": "unknown"}, None

        if device.values.get("d_inverter_type") != MODEL_ID:
            return {"base": "unsupported_device"}, None
        serial = device.values.get("d_serial")
        if not serial:
            return {"base": "invalid_serial"}, None
        return {}, str(serial)
