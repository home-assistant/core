"""Config flow for the BLE Tracker."""

import base64
import binascii
import logging
from typing import override

import probatio

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import async_last_service_info

_LOGGER = logging.getLogger(__name__)

CONF_IRK = "irk"


def _parse_irk(irk: str) -> bytes | None:
    irk = irk.removeprefix("irk:")

    if irk.endswith("="):
        try:
            irk_bytes = bytes(reversed(base64.b64decode(irk)))
        except binascii.Error:
            # IRK is not valid base64
            return None
    else:
        try:
            irk_bytes = binascii.unhexlify(irk)
        except binascii.Error:
            # IRK is not correctly hex encoded
            return None

    if len(irk_bytes) != 16:
        # IRK must be 16 bytes when decoded
        return None

    return irk_bytes


@callback
def _async_migrate_irk(
    hass: HomeAssistant, entry: ConfigEntry, old_irk: str, new_irk: str
) -> None:
    """Move this entry's entities and device from one IRK to another.

    The IRK is part of every unique_id and the device identifier. Only this
    entry's own entries are touched: other integrations can attach to the
    same identifier.
    """
    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if old_irk in entity.unique_id:
            ent_reg.async_update_entity(
                entity.entity_id,
                new_unique_id=entity.unique_id.replace(old_irk, new_irk),
            )
    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if (DOMAIN, old_irk) in device.identifiers:
            dev_reg.async_update_device(
                device.id,
                new_identifiers=(device.identifiers - {(DOMAIN, old_irk)})
                | {(DOMAIN, new_irk)},
            )


class BLEDeviceTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE Device Tracker."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Set up by user."""
        errors: dict[str, str] = {}

        if not bluetooth.async_scanner_count(self.hass, connectable=False):
            return self.async_abort(reason="bluetooth_not_available")

        if user_input is not None:
            irk = user_input[CONF_IRK]

            if not (irk_bytes := _parse_irk(irk)):
                errors[CONF_IRK] = "irk_not_valid"
            elif not (service_info := async_last_service_info(self.hass, irk_bytes)):
                errors[CONF_IRK] = "irk_not_found"
            else:
                await self.async_set_unique_id(irk_bytes.hex())
                return self.async_create_entry(
                    title=service_info.name or "BLE Device Tracker",
                    data={CONF_IRK: irk_bytes.hex()},
                )

        data_schema = probatio.Schema({probatio.Required(CONF_IRK): str})
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Replace the IRK, e.g. after the device was reset."""
        errors: dict[str, str] = {}

        if not bluetooth.async_scanner_count(self.hass, connectable=False):
            return self.async_abort(reason="bluetooth_not_available")

        if user_input is not None:
            if not (irk_bytes := _parse_irk(user_input[CONF_IRK])):
                errors[CONF_IRK] = "irk_not_valid"
            elif not async_last_service_info(self.hass, irk_bytes):
                errors[CONF_IRK] = "irk_not_found"
            else:
                new_irk = irk_bytes.hex()
                entry = self._get_reconfigure_entry()
                if new_irk == entry.data[CONF_IRK]:
                    # The IRK it already has: nothing to move.
                    return self.async_abort(reason="reconfigure_successful")
                # Reserves the IRK: another flow moving an entry to it aborts.
                await self.async_set_unique_id(new_irk)
                self._async_abort_entries_match({CONF_IRK: new_irk})
                # Unloaded while the registries move, so no live entity
                # still carries the old unique_id. If it will not unload,
                # nothing is moved: its entities are still live.
                if not await self.hass.config_entries.async_unload(entry.entry_id):
                    return self.async_abort(reason="unload_failed")
                _async_migrate_irk(self.hass, entry, entry.data[CONF_IRK], new_irk)
                return self.async_update_reload_and_abort(
                    entry, unique_id=new_irk, data_updates={CONF_IRK: new_irk}
                )

        data_schema = probatio.Schema({probatio.Required(CONF_IRK): str})
        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )
