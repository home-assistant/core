"""Repairs for MQTT."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .config_flow import try_connection
from .const import DEFAULT_PORT, DOMAIN, PROTOCOL_5

URL_MQTT_BROKER_CONFIGURATION = (
    "https://www.home-assistant.io/integrations/mqtt/#broker-configuration"
)


class MQTTDeviceEntryMigration(RepairsFlow):
    """Handler to remove subentry for migrated MQTT device."""

    def __init__(self, entry_id: str, subentry_id: str, name: str) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id
        self.subentry_id = subentry_id
        self.name = name

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            device_registry = dr.async_get(self.hass)
            subentry_device = device_registry.async_get_device(
                identifiers={(DOMAIN, self.subentry_id)}
            )
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if TYPE_CHECKING:
                assert entry is not None
                assert subentry_device is not None
            self.hass.config_entries.async_remove_subentry(entry, self.subentry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"name": self.name},
        )


class MQTTProtocolV5Migration(RepairsFlow):
    """Handler to migrate to MQTT protocol version 5."""

    def __init__(self, entry_id: str, broker: str, protocol: str) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id
        self.broker = broker
        self.protocol = protocol

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if TYPE_CHECKING:
                assert entry is not None
            new_entry_data = entry.data.copy()
            new_entry_data[CONF_PROTOCOL] = PROTOCOL_5
            # Try the connection with protocol version 5
            if await self.hass.async_add_executor_job(
                try_connection,
                {CONF_PORT: DEFAULT_PORT} | new_entry_data,
            ):
                self.hass.config_entries.async_update_entry(entry, data=new_entry_data)
                return self.async_create_entry(data={})

            return self.async_abort(
                reason="mqtt_broker_migration_to_v5_failed",
                description_placeholders={
                    "broker": self.broker,
                    "protocol": self.protocol,
                    "url_mqtt_broker_configuration": URL_MQTT_BROKER_CONFIGURATION,
                },
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"broker": self.broker, "protocol": self.protocol},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert data is not None
    entry_id: str = data["entry_id"]  # type: ignore[assignment]
    if issue_id == "protocol_5_migration":
        broker: str = data["broker"]  # type: ignore[assignment]
        protocol: str = data["protocol"]  # type: ignore[assignment]
        return MQTTProtocolV5Migration(entry_id, broker, protocol)
    subentry_id: str = data["subentry_id"]  # type: ignore[assignment]
    name: str = data["name"]  # type: ignore[assignment]
    return MQTTDeviceEntryMigration(
        entry_id=entry_id,
        subentry_id=subentry_id,
        name=name,
    )
