"""Repairs implementation for the esphome integration."""

from typing import cast

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .const import CONF_ALLOW_SERVICE_CALLS
from .manager import async_replace_device


class ESPHomeRepair(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str | int | float | None] | None) -> None:
        """Initialize."""
        self._data = data
        super().__init__()


class DeviceConflictRepair(ESPHomeRepair):
    """Handler for an issue fixing device conflict."""

    @property
    def entry_id(self) -> str:
        """Return the config entry id."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["entry_id"])

    @property
    def mac(self) -> str:
        """Return the MAC address of the new device."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["mac"])

    @property
    def stored_mac(self) -> str:
        """Return the MAC address of the stored device."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["stored_mac"])

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["migrate", "manual"],
        )

    async def async_step_migrate(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the migrate step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="migrate",
                data_schema=vol.Schema({}),
            )
        entry_id = self.entry_id
        await async_replace_device(self.hass, entry_id, self.stored_mac, self.mac)
        self.hass.config_entries.async_schedule_reload(entry_id)
        return self.async_create_entry(data={})

    async def async_step_manual(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the manual step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({}),
            )
        self.hass.config_entries.async_schedule_reload(self.entry_id)
        return self.async_create_entry(data={})


class ServiceCallsRepair(ESPHomeRepair):
    """Handler for enabling Home Assistant actions for a device."""

    @property
    def entry_id(self) -> str:
        """Return the config entry id."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["entry_id"])

    @property
    def name(self) -> str:
        """Return the name of the device."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["name"])

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["enable", "ignore"],
            description_placeholders={"name": self.name},
        )

    async def async_step_enable(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Allow the device to perform Home Assistant actions."""
        if user_input is None:
            return self.async_show_form(
                step_id="enable",
                data_schema=vol.Schema({}),
                description_placeholders={"name": self.name},
            )
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        assert entry is not None
        self.hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_ALLOW_SERVICE_CALLS: True},
        )
        self.hass.config_entries.async_schedule_reload(self.entry_id)
        return self.async_create_entry(data={})

    async def async_step_ignore(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Dismiss the issue without enabling Home Assistant actions."""
        if user_input is None:
            return self.async_show_form(
                step_id="ignore",
                data_schema=vol.Schema({}),
                description_placeholders={"name": self.name},
            )
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("device_conflict"):
        return DeviceConflictRepair(data)
    if issue_id.startswith("service_calls_not_enabled"):
        return ServiceCallsRepair(data)
    # If ESPHome adds confirm-only repairs in the future, this should be changed
    # to return a ConfirmRepairFlow instead of raising a ValueError
    raise ValueError(f"unknown repair {issue_id}")
