"""Repairs platform for the Wake on LAN integration."""

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

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
        turn_off_action: list[dict[str, Any]] | None = self._data.get(CONF_OFF_ACTION)
        name: str = self._data[CONF_NAME]

        if user_input is not None:
            entity_reg = er.async_get(self.hass)
            ping_entry_id: str | None = None

            # Setup ping sensor if host is provided
            if ping_host:
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

            ping_entity_id = None
            for _ in range(10):
                # Wait for ping config entry entity to be created
                if ping_entry_id and (
                    entities := er.async_entries_for_config_entry(
                        entity_reg,
                        ping_entry_id,
                    )
                ):
                    for entity in entities:
                        if entity.domain == "binary_sensor":
                            ping_entity_id = entity.entity_id
                            break
                    break
                await asyncio.sleep(1)
            if not ping_entity_id:
                return self.async_abort(reason="could_not_get_ping_entity")

            # Import Wake on LAN config to get a config entry with a button entity
            config = {
                CONF_MAC: mac,
                CONF_BROADCAST_ADDRESS: broadcast_address,
                CONF_BROADCAST_PORT: broadcast_port,
            }
            import_result = await self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config,
            )
            if not (
                import_result["type"] is FlowResultType.CREATE_ENTRY
                or (
                    import_result["type"] is FlowResultType.ABORT
                    and import_result["reason"] == "already_configured"
                )
            ):
                return self.async_abort(reason="could_not_import_wol")

            wol_entity_id = None
            for _ in range(10):
                # Wait for wol config entry entity to be created
                if entities := er.async_entries_for_config_entry(
                    entity_reg,
                    import_result["result"].entry_id,
                ):
                    wol_entity_id = entities[0].entity_id
                    break
                await asyncio.sleep(1)
            if not wol_entity_id:
                return self.async_abort(reason="could_not_get_wol_entity")

            template_config = {
                CONF_NAME: name,
                CONF_OPTIMISTIC: bool(ping_host),
                CONF_ON_ACTION: {
                    "action": "button.press",
                    "target": {
                        "entity_id": wol_entity_id,
                    },
                },
            }
            if ping_entity_id:
                template_config[CONF_STATE] = (
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

            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="migrate",
            data_schema=vol.Schema({}),
            description_placeholders={"title": name},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow."""
    if data:
        return MigrateSwitchFlow(data)

    return ConfirmRepairFlow()
