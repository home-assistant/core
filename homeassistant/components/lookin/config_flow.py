"""The lookin integration config_flow."""
from __future__ import annotations

from typing import Any

from aiolookin import Device, DeviceNotFound, LookInHttpProtocol, NoUsableService
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN, LOGGER

ADD_NEW_DEVICE_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})


class LookinFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for lookin."""

    def __init__(self) -> None:
        """Init the lookin flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._device_id: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Start a discovery flow from zeroconf."""
        uid: str = discovery_info["hostname"][: -len(".local.")]
        self._host = discovery_info["host"]

        if not uid:
            return self.async_abort(reason="no_uid")

        await self.async_set_unique_id(uid.upper())
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
            }
        )

        assert self._host is not None
        try:
            device: Device = await self._validate_device(host=self._host)
        except (DeviceNotFound, NoUsableService):
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        else:
            self._name = device.name

        self._set_confirm_only()
        self.context["title_placeholders"] = {"name": self._name, "host": self._host}
        return await self.async_step_discovery_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """User initiated discover flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_IP_ADDRESS]
            try:
                device = await self._validate_device(host=host)
            except (DeviceNotFound, NoUsableService):
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._name = device.name
                self._host = host
                self._device_id = device.id
                await self.async_set_unique_id(
                    device.id.upper(), raise_on_progress=False
                )
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: self._host,
                    }
                )
                return await self.async_step_discovery_confirm()

        return self.async_show_form(
            step_id="user", data_schema=ADD_NEW_DEVICE_SCHEMA, errors=errors
        )

    async def _validate_device(self, host: str) -> Device:
        """Validate we can connect to the device."""
        lookin_protocol = LookInHttpProtocol(
            host=host, session=async_get_clientsession(self.hass)
        )
        return await lookin_protocol.get_info()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the discover flow."""
        if user_input is None:
            self.context["title_placeholders"] = {
                "name": self._name,
                "host": self._host,
            }
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={"name": self._name, "host": self._host},
            )

        assert self._name is not None
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_NAME: self._name,
                CONF_HOST: self._host,
                CONF_DEVICE_ID: self._device_id,
            },
        )
