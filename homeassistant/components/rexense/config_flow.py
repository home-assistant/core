"""Config flow for Rexense integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RexenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rexense."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.device_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual user configuration (from UI)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            try:
                session = aiohttp_client.async_get_clientsession(self.hass)
                url = f"http://{host}:{port}/rex/device/v1/operate"
                # parameter {"Version":"1.0","VendorCode":"Rexense","Timestamp":"{Time}","Seq":"{Seq}","DeviceId":"{GwId}","FunctionCode":"GetBasicInfo","Payload":{}}
                get_basic_info = {
                    "Version": "1.0",
                    "VendorCode": "Rexense",
                    "Timestamp": "0",
                    "Seq": "0",
                    "DeviceId": "",
                    "FunctionCode": "GetBasicInfo",
                    "Payload": {},
                }
                _LOGGER.debug(
                    "Fetching Rexense device info from %s:%s", url, get_basic_info
                )
                async with asyncio.timeout(5):
                    resp = await session.get(url, json=get_basic_info)
                if resp.status != 200:
                    _LOGGER.error(
                        "Device at %s responded with status %s", host, resp.status
                    )
                    errors["base"] = "cannot_connect"
                else:
                    data = await resp.json()
                    device_id = data.get("DeviceId")
                    function = data.get("FunctionCode")
                    payload = data.get("Payload")
                    if function != "ReportBasicInfo" or not payload:
                        _LOGGER.error("Invalid response format: %s", data)
                        errors["base"] = "cannot_connect"
                        return self.async_show_form(
                            step_id="user",
                            data_schema=vol.Schema(
                                {
                                    vol.Required(CONF_HOST): cv.string,
                                    vol.Optional(
                                        CONF_PORT, default=DEFAULT_PORT
                                    ): cv.port,
                                }
                            ),
                            errors=errors,
                        )
                    model = data.get("ModelId")
                    sw_build_id = data.get("SwBuildId", "")
                    if not device_id or not model:
                        _LOGGER.error("Invalid device info response: %s", data)
                        errors["base"] = "cannot_connect"

                    feature_map = payload.get("FeatureMap")

                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host, CONF_PORT: port}
                    )

                    _LOGGER.debug(
                        "Step by user discovered device id: %s, model: %s, feature_map: %s",
                        device_id,
                        model,
                        feature_map,
                    )

                    return self.async_create_entry(
                        title=f"{model} ({device_id})",
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            "model": model,
                            "sw_build_id": sw_build_id,
                            "feature_map": feature_map,
                        },
                    )
            except (TimeoutError, ClientError) as err:
                _LOGGER.error(
                    "Error connecting to Rexense device at %s:%s - %s", host, port, err
                )
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        host: str
        port: int
        model: str
        device_id: str
        sw_build_id: str
        feature_map: list[Any]

        # Retrieve the ConfigEntry being reconfigured
        entry_id = self.context.get("entry_id")
        if not entry_id:
            # Should never happen, but abort if we can't find it
            return self.async_abort(reason="unknown")

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="unknown")

        # On form submission, write back updated data
        if user_input is not None:
            host = self.device_data[CONF_HOST]
            port = self.device_data.get(CONF_PORT, DEFAULT_PORT)
            device_id = str(self.device_data.get("device_id", ""))
            model = self.device_data.get("model", "Rexense Device")
            sw_build_id = self.device_data.get("sw_build_id", "")
            feature_map = self.device_data.get("feature_map", [])
            # Update the entry with new data
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                    "model": model,
                    "sw_build_id": sw_build_id,
                    "feature_map": feature_map,
                },
            )

        # Populate self.device_data so downstream steps can read it
        host = entry.data[CONF_HOST]
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        model = entry.data.get("model", "Rexense Device")
        device_id = str(entry.data.get("device_id", ""))
        sw_build_id = entry.data.get("sw_build_id", "")
        feature_map = entry.data.get("feature_map", [])

        self.device_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            "model": model,
            "device_id": device_id,
            "sw_build_id": sw_build_id,
            "feature_map": feature_map,
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=host): cv.string,
                vol.Optional(CONF_PORT, default=port): cv.port,
            }
        )
        _LOGGER.debug("Reconfiguring Rexense device %s at %s:%s", device_id, host, port)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            description_placeholders={
                "device_id": device_id,
                "model": model,
                "host": host,
            },
            errors={},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf discovery.

        Args:
            discovery_info: ZeroconfServiceInfo object describing the discovered service.

        Returns:
            A ConfigFlowResult for the discovery process.

        """
        if discovery_info.type != "_rexense._tcp.local.":
            _LOGGER.debug("Ignore non Rexense services: %s", discovery_info.type)
            return self.async_abort(reason="not_rexense_service")
        host = discovery_info.host or (
            discovery_info.addresses[0] if discovery_info.addresses else None
        )
        if host is None:
            _LOGGER.error("Host info not found: %s", discovery_info)
            return self.async_abort(reason="no_host_found")
        port: int = discovery_info.port or DEFAULT_PORT
        _LOGGER.debug("Discovered Rexense device via Zeroconf: %s", discovery_info)
        _LOGGER.debug("Host: %s, Port: %s", host, port)
        if not host:
            return self.async_abort(reason="cannot_connect")

        session = aiohttp_client.async_get_clientsession(self.hass)
        url = f"http://{host}:{port}/rex/device/v1/operate"
        # parameter {"Version":"1.0","VendorCode":"Rexense","Timestamp":"{Time}","Seq":"{Seq}","DeviceId":"{GwId}","FunctionCode":"GetBasicInfo","Payload":{}}
        get_basic_info = {
            "Version": "1.0",
            "VendorCode": "Rexense",
            "Timestamp": "0",
            "Seq": "0",
            "DeviceId": "",
            "FunctionCode": "GetBasicInfo",
            "Payload": {},
        }
        data: dict[str, Any] | None = None
        # Retry a few times in case the device is still booting
        for attempt in range(5):
            try:
                async with asyncio.timeout(5):
                    resp = await session.get(url, json=get_basic_info)
                if resp.status == 200:
                    data = await resp.json()
                    break
                _LOGGER.warning(
                    "Attempt %d: unexpected status %s from %s, retrying…",
                    attempt + 1,
                    resp.status,
                    host,
                )
            except (TimeoutError, ClientError) as err:
                _LOGGER.warning(
                    "Attempt %d: cannot connect to %s - %s, retrying…",
                    attempt + 1,
                    url,
                    err,
                )
            await asyncio.sleep(1)
        if not data:
            _LOGGER.error("Failed to fetch basic info after retries: %s", url)
            return self.async_abort(reason="cannot_connect")

        function = data.get("FunctionCode")
        payload = data.get("Payload")
        device_id = data.get("DeviceId")

        if function != "ReportBasicInfo" or not payload:
            _LOGGER.error("Invalid response format: %s", data)
            return self.async_abort(reason="cannot_connect")

        model = payload.get("ModelId")

        if not device_id or not model:
            return self.async_abort(reason="cannot_connect")

        feature_map = payload.get("FeatureMap")

        _LOGGER.debug(
            "Discovered device ID: %s, Model: %s, FeatureMap: %s",
            device_id,
            model,
            feature_map,
        )

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})

        self.device_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            "device_id": device_id,
            "model": model,
            "feature_map": feature_map,
        }

        self.context.update(
            {"title_placeholders": {"model": model, "device_id": device_id}}
        )

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the confirmation step for discovered device."""
        if user_input is not None:
            host = self.device_data[CONF_HOST]
            port = self.device_data.get(CONF_PORT, DEFAULT_PORT)
            device_id = self.device_data.get("device_id")
            model = self.device_data.get("model", "Rexense Device")
            sw_build_id = self.device_data.get("sw_build_id", "")
            feature_map = self.device_data.get("feature_map", [])
            return self.async_create_entry(
                title=f"{model} ({device_id})" if device_id else model,
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                    "model": model,
                    "sw_build_id": sw_build_id,
                    "feature_map": feature_map,
                },
            )

        host = self.device_data[CONF_HOST]
        model = self.device_data.get("model", "Rexense Device")
        _LOGGER.debug("Showing discovery confirmation for device %s (%s)", host, model)
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={CONF_MODEL: model, CONF_HOST: host},
            errors={},
        )
