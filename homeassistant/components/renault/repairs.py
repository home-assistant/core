"""Repairs for the Renault integration."""

from typing import TYPE_CHECKING, Any

import aiohttp
import probatio
from renault_api.exceptions import NotAuthenticatedException
from renault_api.gigya.exceptions import GigyaException
from renault_api.kamereon.exceptions import KamereonResponseException

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, RenaultConfigurationKeys
from .renault_hub import RenaultHub

if TYPE_CHECKING:
    from . import RenaultConfigEntry


class AccountNotFoundRepairFlow(RepairsFlow):
    """Move a config entry to the new Kamereon account of its vehicles."""

    def __init__(self, entry: RenaultConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the repair flow."""
        return await self.async_step_account()

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Select the new Kamereon account."""
        old_account_id = self._entry.data[RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID]
        if user_input is not None:
            new_account_id = user_input[RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID]
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={
                    **self._entry.data,
                    RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID: new_account_id,
                },
                unique_id=new_account_id,
                # The entry title defaults to the account id.
                title=new_account_id
                if self._entry.title == old_account_id
                else self._entry.title,
            )
            self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
            return self.async_create_entry(data={})

        device_registry = dr.async_get(self.hass)
        vins = {
            identifier[1]
            for device in dr.async_entries_for_config_entry(
                device_registry, self._entry.entry_id
            )
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        }
        hub = RenaultHub(self.hass, self._entry.data[RenaultConfigurationKeys.LOCALE])
        try:
            await hub.async_login(self._entry)
            account_ids = await hub.get_account_ids_for_vins(vins)
        except NotAuthenticatedException:
            self._entry.async_start_reauth(self.hass)
            return self.async_abort(reason="reauth_required")
        except aiohttp.ClientError, GigyaException, KamereonResponseException:
            return self.async_abort(reason="cannot_connect")

        configured_account_ids = {
            entry.unique_id for entry in self.hass.config_entries.async_entries(DOMAIN)
        }
        candidates = [
            account_id
            for account_id in account_ids
            if account_id not in configured_account_ids
        ]
        if not candidates:
            return self.async_abort(
                reason="no_new_account",
                description_placeholders={"account_id": old_account_id},
            )

        return self.async_show_form(
            step_id="account",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID,
                        default=candidates[0],
                    ): probatio.In(candidates)
                }
            ),
            description_placeholders={"account_id": old_account_id},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the repair flow for a Kamereon account that no longer exists."""
    assert data
    return AccountNotFoundRepairFlow(
        hass.config_entries.async_get_known_entry(data["entry_id"])
    )
