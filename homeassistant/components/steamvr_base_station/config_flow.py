"""Config flow for SteamVR Base Station."""

import logging
from typing import Any, override

from lighthouse_ble import BaseStationV2, LighthouseError, Version, parse_advertisement
import probatio

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _is_v2_station(info: BluetoothServiceInfoBleak) -> bool:
    advertisement = parse_advertisement(info.name, info.manufacturer_data)
    return advertisement is not None and advertisement.version is Version.V2


async def _test_connection(hass: HomeAssistant, address: str) -> str | None:
    """Read the station's device information; return an error key on failure."""
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        return "cannot_connect"
    try:
        await BaseStationV2(ble_device).read_device_info()
    except LighthouseError:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error while connecting to %s", address)
        return "unknown"
    return None


class SteamVRBaseStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SteamVR Base Station."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a station found by the bluetooth integration."""
        if not _is_v2_station(discovery_info):
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setting up a discovered station."""
        assert self._discovery is not None
        errors: dict[str, str] = {}
        # The station is only contacted once the user confirms, so discovery of
        # every station in range does not use up connection slots.
        if user_input is not None:
            error = await _test_connection(self.hass, self._discovery.address)
            if error is None:
                return self.async_create_entry(title=self._discovery.name, data={})
            errors["base"] = error
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one of the stations currently in range."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if (error := await _test_connection(self.hass, address)) is None:
                return self.async_create_entry(
                    title=self._discovered[address].name, data={}
                )
            errors["base"] = error
        else:
            configured = self._async_current_ids(include_ignore=False)
            for info in async_discovered_service_info(self.hass, connectable=True):
                if (
                    info.address not in configured
                    and info.address not in self._discovered
                    and _is_v2_station(info)
                ):
                    self._discovered[info.address] = info

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            address: f"{info.name} ({address})"
                            for address, info in self._discovered.items()
                        }
                    )
                }
            ),
            errors=errors,
        )
