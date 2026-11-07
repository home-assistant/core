"""Repairs platform for the Wake on LAN integration."""

import asyncio
from typing import Any

import probatio

from homeassistant import config as conf_util
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import UNDEFINED

from .const import CONF_OFF_ACTION, CONF_ON_ACTION, DOMAIN


class MigrateSwitchFlow(RepairsFlow):
    """Repair flow to migrate switch to a template switch."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Create flow."""
        self._data = data
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_migrate()

    async def async_step_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the migration step of a fix flow."""
        ping_host: str | None = self._data.get(CONF_HOST)
        mac: str = self._data[CONF_MAC]
        broadcast_address: str | None = self._data.get(CONF_BROADCAST_ADDRESS)
        broadcast_port: int | None = self._data.get(CONF_BROADCAST_PORT)
        name: str = self._data[CONF_NAME]

        if user_input is None:
            return self.async_show_form(
                step_id="migrate",
                data_schema=probatio.Schema({}),
                description_placeholders={"mac": mac},
            )

        # The validated off action holds objects that can't be stored as JSON
        try:
            turn_off_action = await self._async_get_raw_turn_off_action(mac)
        except HomeAssistantError:
            return self.async_abort(reason="could_not_read_configuration")

        entity_reg = er.async_get(self.hass)

        ping_entity_id = None
        if ping_host:
            # Ping strips the host before storing it
            ping_entry_id, _ = await self._async_get_or_import_entry(
                "ping", {CONF_HOST: ping_host.strip()}, {CONF_HOST: ping_host}
            )
            if not ping_entry_id:
                return self.async_abort(reason="could_not_import_host")
            ping_entity_id = await self._async_wait_for_entity(
                entity_reg, ping_entry_id, BINARY_SENSOR_DOMAIN
            )
            if not ping_entity_id:
                return self.async_abort(reason="could_not_get_ping_entity")

        wol_config: dict[str, Any] = {CONF_MAC: mac}
        if broadcast_address is not None:
            wol_config[CONF_BROADCAST_ADDRESS] = broadcast_address
        if broadcast_port is not None:
            wol_config[CONF_BROADCAST_PORT] = broadcast_port
        wol_entry_id, _ = await self._async_get_or_import_entry(
            DOMAIN, {CONF_MAC: dr.format_mac(mac)}, wol_config
        )
        if not wol_entry_id:
            return self.async_abort(reason="could_not_import_wol")

        wol_entity_id = await self._async_wait_for_entity(
            entity_reg, wol_entry_id, BUTTON_DOMAIN
        )
        if not wol_entity_id:
            return self.async_abort(reason="could_not_get_wol_entity")

        # Create the Template switch based on the above entities created
        template_config = {
            CONF_NAME: name,
            CONF_ON_ACTION: [
                {
                    "action": "button.press",
                    "target": {
                        "entity_id": wol_entity_id,
                    },
                }
            ],
        }
        if ping_entity_id:
            template_config[CONF_VALUE_TEMPLATE] = (
                "{{ is_state('" + ping_entity_id + "', 'on') }}"
            )
        if turn_off_action:
            template_config[CONF_OFF_ACTION] = turn_off_action

        # Same matching as the Template import, missing keys must be missing
        template_match = {
            key: template_config.get(key)
            for key in (CONF_ON_ACTION, CONF_OFF_ACTION, CONF_VALUE_TEMPLATE)
        } | {"template_type": SWITCH_DOMAIN}
        template_entry_id, template_created = await self._async_get_or_import_entry(
            "template", template_match, template_config
        )
        if not template_entry_id:
            return self.async_abort(reason="could_not_import_template")
        old_entity_id = entity_reg.async_get_entity_id(
            SWITCH_DOMAIN, DOMAIN, dr.format_mac(mac)
        )

        if not template_created:
            # The existing switch may be referenced by its own ID, so keep it
            existing_entity_id = next(
                (
                    entity.entity_id
                    for entity in er.async_entries_for_config_entry(
                        entity_reg, template_entry_id
                    )
                    if entity.domain == SWITCH_DOMAIN
                ),
                name,
            )
            return self.async_create_entry(
                data={},
                description="existing_template",
                description_placeholders={
                    "mac": mac,
                    "entity_id": existing_entity_id,
                    "old_entity_id": old_entity_id or name,
                },
            )

        template_entity_id = await self._async_wait_for_entity(
            entity_reg, template_entry_id, SWITCH_DOMAIN
        )
        if not template_entity_id:
            return self.async_abort(reason="could_not_get_template_entity")
        if old_entity_id:
            self._async_take_over_entity(entity_reg, old_entity_id, template_entity_id)

        return self.async_create_entry(
            data={},
            description="with_ping" if ping_host else "no_ping",
            description_placeholders={"mac": mac, "host": ping_host or ""},
        )

    async def _async_get_or_import_entry(
        self, domain: str, match: dict[str, Any], import_data: dict[str, Any]
    ) -> tuple[str | None, bool]:
        """Return the ID of the matching config entry and if it was created.

        The entry is imported when no entry has options matching all of `match`.
        """

        def find_entry_id() -> str | None:
            return next(
                (
                    entry.entry_id
                    for entry in self.hass.config_entries.async_entries(domain)
                    if all(
                        entry.options.get(key) == value for key, value in match.items()
                    )
                ),
                None,
            )

        if entry_id := find_entry_id():
            return entry_id, False
        result = await self.hass.config_entries.flow.async_init(
            domain, context={"source": SOURCE_IMPORT}, data=import_data
        )
        if result["type"] is FlowResultType.CREATE_ENTRY:
            return result["result"].entry_id, True
        if (
            result["type"] is FlowResultType.ABORT
            and result["reason"] == "already_configured"
        ):
            # Abort results don't carry the existing entry
            return find_entry_id(), False
        return None, False

    async def _async_wait_for_entity(
        self, entity_reg: er.EntityRegistry, entry_id: str, domain: str
    ) -> str | None:
        """Return the entity ID of the config entry's entity once it is registered.

        A disabled entity is enabled, as the Template switch depends on it.
        """
        for _ in range(10):
            for entity in er.async_entries_for_config_entry(entity_reg, entry_id):
                if entity.domain != domain:
                    continue
                if entity.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY:
                    return None
                if entity.disabled:
                    entity_reg.async_update_entity(entity.entity_id, disabled_by=None)
                return entity.entity_id
            await asyncio.sleep(1)
        return None

    @callback
    def _async_take_over_entity(
        self,
        entity_reg: er.EntityRegistry,
        old_entity_id: str,
        new_entity_id: str,
    ) -> None:
        """Move entity ID and user customizations from the WOL to the Template switch."""
        if (old_entry := entity_reg.async_get(old_entity_id)) is None:
            return
        entity_reg.async_remove(old_entity_id)
        entity_reg.async_update_entity(
            new_entity_id,
            new_entity_id=old_entity_id,
            aliases=old_entry.aliases,
            area_id=old_entry.area_id,
            categories=dict(old_entry.categories),
            icon=old_entry.icon,
            labels=set(old_entry.labels),
            name=old_entry.name,
            disabled_by=(
                old_entry.disabled_by
                if old_entry.disabled_by is er.RegistryEntryDisabler.USER
                else UNDEFINED
            ),
            hidden_by=(
                old_entry.hidden_by
                if old_entry.hidden_by is er.RegistryEntryHider.USER
                else UNDEFINED
            ),
        )
        for domain, options in old_entry.options.items():
            entity_reg.async_update_entity_options(old_entity_id, domain, options)

    async def _async_get_raw_turn_off_action(self, mac: str) -> Any | None:
        """Return the unvalidated off action of the YAML switch for this MAC."""
        config = await conf_util.async_hass_config_yaml(self.hass)
        for platform, platform_config in conf_util.config_per_platform(
            config, SWITCH_DOMAIN
        ):
            if platform == DOMAIN and dr.format_mac(
                str(platform_config.get(CONF_MAC))
            ) == dr.format_mac(mac):
                return platform_config.get(CONF_OFF_ACTION)
        return None


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow."""
    if data:
        return MigrateSwitchFlow(data)

    return ConfirmRepairFlow()
