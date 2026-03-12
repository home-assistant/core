"""Repairs for KNX integration."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol
from xknx.exceptions.exception import InvalidSecureConfiguration
from xknx.telegram import GroupAddress, IndividualAddress, Telegram

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir, selector
from homeassistant.helpers.dispatcher import async_dispatcher_connect

if TYPE_CHECKING:
    from .knx_module import KNXModule

from .const import (
    CONF_KNX_KNXKEY_PASSWORD,
    DOMAIN,
    REPAIR_ISSUE_DATA_SECURE_GROUP_KEY,
    KNXConfigEntryData,
)
from .storage.keyring import DEFAULT_KNX_KEYRING_FILENAME, save_uploaded_knxkeys_file
from .telegrams import SIGNAL_KNX_DATA_SECURE_ISSUE_TELEGRAM, TelegramDict

CONF_KEYRING_FILE: Final = "knxkeys_file"


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == REPAIR_ISSUE_DATA_SECURE_GROUP_KEY:
        return DataSecureGroupIssueRepairFlow()
    # If KNX adds confirm-only repairs in the future, this should be changed
    # to return a ConfirmRepairFlow instead of raising a ValueError
    raise ValueError(f"unknown repair {issue_id}")


######################
# DataSecure key issue
######################


@callback
def data_secure_group_key_issue_dispatcher(knx_module: KNXModule) -> Callable[[], None]:
    """Watcher for DataSecure group key issues."""
    return async_dispatcher_connect(
        knx_module.hass,
        signal=SIGNAL_KNX_DATA_SECURE_ISSUE_TELEGRAM,
        target=partial(_data_secure_group_key_issue_handler, knx_module),
    )


@callback
def _data_secure_group_key_issue_handler(
    knx_module: KNXModule, telegram: Telegram, telegram_dict: TelegramDict
) -> None:
    """Handle DataSecure group key issue telegrams."""
    if telegram.destination_address not in knx_module.group_address_entities:
        # Only report issues for configured group addresses
        return

    issue_registry = ir.async_get(knx_module.hass)
    new_ga = str(telegram.destination_address)
    new_ia = str(telegram.source_address)
    new_data = {new_ga: new_ia}

    if existing_issue := issue_registry.async_get_issue(
        DOMAIN, REPAIR_ISSUE_DATA_SECURE_GROUP_KEY
    ):
        assert isinstance(existing_issue.data, dict)
        existing_data: dict[str, str] = existing_issue.data  # type: ignore[assignment]
        if new_ga in existing_data:
            current_ias = existing_data[new_ga].split(", ")
            if new_ia in current_ias:
                return
            current_ias = sorted([*current_ias, new_ia], key=IndividualAddress)
            new_data[new_ga] = ", ".join(current_ias)
        new_data_unsorted = existing_data | new_data
        new_data = {
            key: new_data_unsorted[key]
            for key in sorted(new_data_unsorted, key=GroupAddress)
        }

    issue_registry.async_get_or_create(
        DOMAIN,
        REPAIR_ISSUE_DATA_SECURE_GROUP_KEY,
        data=new_data,  # type: ignore[arg-type]
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=REPAIR_ISSUE_DATA_SECURE_GROUP_KEY,
        translation_placeholders={
            "addresses": "\n".join(
                f"`{ga}` from {ias}" for ga, ias in new_data.items()
            ),
            "interface": str(knx_module.xknx.current_address),
        },
    )


class DataSecureGroupIssueRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow for outdated DataSecure keys."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_secure_knxkeys()

    async def async_step_secure_knxkeys(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Manage upload of new KNX Keyring file."""
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_KNX_KNXKEY_PASSWORD]
            keyring = None
            try:
                keyring = await save_uploaded_knxkeys_file(
                    self.hass,
                    uploaded_file_id=user_input[CONF_KEYRING_FILE],
                    password=password,
                )
            except InvalidSecureConfiguration:
                errors[CONF_KNX_KNXKEY_PASSWORD] = "keyfile_invalid_signature"

            if not errors and keyring:
                new_entry_data = KNXConfigEntryData(
                    knxkeys_filename=f"{DOMAIN}/{DEFAULT_KNX_KEYRING_FILENAME}",
                    knxkeys_password=password,
                )
                return self.finish_flow(new_entry_data)

        fields = {
            vol.Required(CONF_KEYRING_FILE): selector.FileSelector(
                config=selector.FileSelectorConfig(accept=".knxkeys")
            ),
            vol.Required(CONF_KNX_KNXKEY_PASSWORD): selector.TextSelector(),
        }
        return self.async_show_form(
            step_id="secure_knxkeys",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    @callback
    def finish_flow(
        self, new_entry_data: KNXConfigEntryData
    ) -> data_entry_flow.FlowResult:
        """Finish the repair flow. Reload the config entry."""
        knx_config_entries = self.hass.config_entries.async_entries(DOMAIN)
        if knx_config_entries:
            config_entry = knx_config_entries[0]  # single_config_entry
            new_data = {**config_entry.data, **new_entry_data}
            self.hass.config_entries.async_update_entry(config_entry, data=new_data)
            self.hass.config_entries.async_schedule_reload(config_entry.entry_id)
        return self.async_create_entry(data={})
