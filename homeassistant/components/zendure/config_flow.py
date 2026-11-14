"""Config flow to configure the Zendure integration."""

from typing import Any, override

import probatio
from zendure import (
    DeviceSnapshot,
    UnsupportedDeviceError,
    ValidationError,
    ZendureError,
    create_local_client,
)
from zendure.catalog import lookup_device

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import DOMAIN, LOGGER


class ZendureFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Zendure config flow."""

    VERSION = 1

    async def _async_validate(
        self, host: str, errors: dict[str, str]
    ) -> DeviceSnapshot | None:
        """Read the device once, recording a form error instead of raising."""
        try:
            async with create_local_client(
                host, async_get_clientsession(self.hass)
            ) as client:
                return await client.async_refresh()
        except ValidationError:
            errors[CONF_HOST] = "invalid_host"
        except UnsupportedDeviceError as err:
            LOGGER.debug(
                "Device at %s reports unsupported product %r", host, err.product
            )
            errors["base"] = "unsupported_device"
        except ZendureError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if snapshot := await self._async_validate(host, errors):
                await self.async_set_unique_id(snapshot.serial_number)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=lookup_device(snapshot.product_raw).display_name,
                    data={CONF_HOST: host},
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST)
                    ): TextSelector(TextSelectorConfig(autocomplete="off")),
                }
            ),
            errors=errors,
        )
