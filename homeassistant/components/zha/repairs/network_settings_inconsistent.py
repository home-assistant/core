"""ZHA repair for inconsistent network settings."""
from __future__ import annotations

import logging
from typing import Any

from zigpy.backups import NetworkBackup

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from ..core.const import DOMAIN
from ..radio_manager import ZhaRadioManager

_LOGGER = logging.getLogger(__name__)

ISSUE_INCONSISTENT_NETWORK_SETTINGS = "inconsistent_network_settings"


def _format_settings_diff(old_state: NetworkBackup, new_state: NetworkBackup) -> str:
    """Format the difference between two network backups."""
    lines: list[str] = []

    def _add_difference(
        lines: list[str], text: str, old: Any, new: Any, pre: bool = True
    ) -> None:
        """Add a line to the list if the values are different."""
        wrap = "`" if pre else ""

        if old != new:
            lines.append(f"{text}: {wrap}{old}{wrap} \u2192 {wrap}{new}{wrap}")

    _add_difference(
        lines,
        "Channel",
        old=old_state.network_info.channel,
        new=new_state.network_info.channel,
        pre=False,
    )
    _add_difference(
        lines,
        "Node IEEE",
        old=old_state.node_info.ieee,
        new=new_state.node_info.ieee,
    )
    _add_difference(
        lines,
        "PAN ID",
        old=old_state.network_info.pan_id,
        new=new_state.network_info.pan_id,
    )
    _add_difference(
        lines,
        "Extended PAN ID",
        old=old_state.network_info.extended_pan_id,
        new=new_state.network_info.extended_pan_id,
    )
    _add_difference(
        lines,
        "NWK update ID",
        old=old_state.network_info.nwk_update_id,
        new=new_state.network_info.nwk_update_id,
        pre=False,
    )
    _add_difference(
        lines,
        "TC Link Key",
        old=old_state.network_info.tc_link_key.key,
        new=new_state.network_info.tc_link_key.key,
    )
    _add_difference(
        lines,
        "Network Key",
        old=old_state.network_info.network_key.key,
        new=new_state.network_info.network_key.key,
    )

    return "\n".join([f"- {line}" for line in lines])


async def warn_on_inconsistent_network_settings(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    old_state: NetworkBackup,
    new_state: NetworkBackup,
) -> None:
    """Create a repair if the network settings are inconsistent with the last backup."""

    ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id=ISSUE_INCONSISTENT_NETWORK_SETTINGS,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_INCONSISTENT_NETWORK_SETTINGS,
        data={
            "config_entry_id": config_entry.entry_id,
            "old_state": old_state.as_dict(),
            "new_state": new_state.as_dict(),
        },
    )


class NetworkSettingsInconsistentFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        """Initialize the flow."""
        self.hass = hass
        self._old_state = NetworkBackup.from_dict(data["old_state"])
        self._new_state = NetworkBackup.from_dict(data["new_state"])

        self._entry_id: str = data["config_entry_id"]

        config_entry = self.hass.config_entries.async_get_entry(self._entry_id)
        assert config_entry is not None
        self._radio_mgr = ZhaRadioManager.from_config_entry(self.hass, config_entry)

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["restore_old_settings", "use_new_settings"],
            description_placeholders={
                "diff": _format_settings_diff(self._old_state, self._new_state)
            },
        )

    async def async_step_use_new_settings(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Step to use the new settings found on the radio."""
        async with self._radio_mgr.connect_zigpy_app() as app:
            app.backups.add_backup(self._new_state)

        await self.hass.config_entries.async_reload(self._entry_id)
        return self.async_create_entry(title="", data={})

    async def async_step_restore_old_settings(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Step to restore the most recent backup."""
        await self._radio_mgr.restore_backup(self._old_state)

        await self.hass.config_entries.async_reload(self._entry_id)
        return self.async_create_entry(title="", data={})
