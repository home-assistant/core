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
        ping_entry_id: str | None = None

        ping_entity_id = None
        if ping_host:
            # If a hosts was provided, setup a Ping config entry
            ping_entry_id = None
            ping_entries = self.hass.config_entries.async_entries("ping")
            for entry in ping_entries:
                if entry.options.get(CONF_HOST) == ping_host:
                    ping_entry_id = entry.entry_id
                    break
            if not ping_entry_id:
                ping_config = {
                    CONF_HOST: ping_host,
                }
                import_result = await self.hass.config_entries.flow.async_init(
                    "ping",
                    context={"source": SOURCE_IMPORT},
                    data=ping_config,
                )
                if not (
                    import_result["type"] is FlowResultType.CREATE_ENTRY
                    or (
                        import_result["type"] is FlowResultType.ABORT
                        and import_result["reason"] == "already_configured"
                    )
                ):
                    return self.async_abort(reason="could_not_import_host")
                ping_entry_id = import_result["result"].entry_id

            ping_entity_id = await self._async_wait_for_entity(
                entity_reg, ping_entry_id, BINARY_SENSOR_DOMAIN
            )
            if not ping_entity_id:
                return self.async_abort(reason="could_not_get_ping_entity")

        # Import Wake on LAN config to get a config entry with a button entity
        wol_entry_id = None
        wol_entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in wol_entries:
            if entry.options.get(CONF_MAC) == dr.format_mac(mac):
                wol_entry_id = entry.entry_id
                break
        if not wol_entry_id:
            wol_config: dict[str, Any] = {CONF_MAC: mac}
            if broadcast_address is not None:
                wol_config[CONF_BROADCAST_ADDRESS] = broadcast_address
            if broadcast_port is not None:
                wol_config[CONF_BROADCAST_PORT] = broadcast_port
            import_result = await self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=wol_config,
            )
            if not (
                import_result["type"] is FlowResultType.CREATE_ENTRY
                or (
                    import_result["type"] is FlowResultType.ABORT
                    and import_result["reason"] == "already_configured"
                )
            ):
                return self.async_abort(reason="could_not_import_wol")
            wol_entry_id = import_result["result"].entry_id

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

        import_result = await self.hass.config_entries.flow.async_init(
            "template",
            context={"source": SOURCE_IMPORT},
            data=template_config,
        )
        if not (
            import_result["type"] is FlowResultType.CREATE_ENTRY
            or (
                import_result["type"] is FlowResultType.ABORT
                and import_result["reason"] == "already_configured"
            )
        ):
            return self.async_abort(reason="could_not_import_template")

        if import_result["type"] is FlowResultType.CREATE_ENTRY and (
            old_entity_id := entity_reg.async_get_entity_id(
                SWITCH_DOMAIN, DOMAIN, dr.format_mac(mac)
            )
        ):
            template_entity_id = await self._async_wait_for_entity(
                entity_reg, import_result["result"].entry_id, SWITCH_DOMAIN
            )
            if not template_entity_id:
                return self.async_abort(reason="could_not_get_template_entity")
            self._async_take_over_entity(entity_reg, old_entity_id, template_entity_id)

        return self.async_create_entry(
            data={},
            description="with_ping" if ping_host else "no_ping",
            description_placeholders={"mac": mac, "host": ping_host or ""},
        )

    async def _async_wait_for_entity(
        self, entity_reg: er.EntityRegistry, entry_id: str, domain: str
    ) -> str | None:
        """Return the entity ID of the config entry's entity once it is registered."""
        for _ in range(10):
            for entity in er.async_entries_for_config_entry(entity_reg, entry_id):
                if entity.domain == domain:
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
