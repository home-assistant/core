"""Config flow for EHEIM Digital."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.hub import EheimDigitalHub
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST, default="eheimdigital.local"): selector.TextSelector()}
)


class EheimDigitalConfigFlow(ConfigFlow, domain=DOMAIN):
    """The EHEIM Digital config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.data: dict[str, Any] = {}
        self.main_device_added_event = asyncio.Event()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.data[CONF_HOST] = host = discovery_info.host

        self._async_abort_entries_match(self.data)

        hub = EheimDigitalHub(
            host=host,
            session=async_get_clientsession(self.hass),
            loop=self.hass.loop,
            main_device_added_event=self.main_device_added_event,
        )
        try:
            await hub.connect()

            async with asyncio.timeout(2):
                # This event gets triggered when the first message is received from
                # the device, it contains the data necessary to create the main device.
                # This removes the race condition where the main device is accessed
                # before the response from the device is parsed.
                await self.main_device_added_event.wait()
                if TYPE_CHECKING:
                    # At this point the main device is always set
                    assert isinstance(hub.main, EheimDigitalDevice)
                await hub.close()
        except (ClientError, TimeoutError):
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001
            return self.async_abort(reason="unknown")
        await self.async_set_unique_id(hub.main.mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.data[CONF_HOST],
                data={CONF_HOST: self.data[CONF_HOST]},
            )

        self._set_confirm_only()
        return self.async_show_form(step_id="discovery_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        if user_input is None:
            return self.async_show_form(step_id=SOURCE_USER, data_schema=CONFIG_SCHEMA)

        self._async_abort_entries_match(user_input)
        errors: dict[str, str] = {}
        hub = EheimDigitalHub(
            host=user_input[CONF_HOST],
            session=async_get_clientsession(self.hass),
            loop=self.hass.loop,
            main_device_added_event=self.main_device_added_event,
        )

        try:
            await hub.connect()

            async with asyncio.timeout(2):
                # This event gets triggered when the first message is received from
                # the device, it contains the data necessary to create the main device.
                # This removes the race condition where the main device is accessed
                # before the response from the device is parsed.
                await self.main_device_added_event.wait()
                if TYPE_CHECKING:
                    # At this point the main device is always set
                    assert isinstance(hub.main, EheimDigitalDevice)
                await self.async_set_unique_id(
                    hub.main.mac_address, raise_on_progress=False
                )
                await hub.close()
        except (ClientError, TimeoutError):
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            errors["base"] = "unknown"
            LOGGER.exception("Unknown exception occurred")
        else:
            self._abort_if_unique_id_configured()
            return self.async_create_entry(data=user_input, title=user_input[CONF_HOST])
        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )
