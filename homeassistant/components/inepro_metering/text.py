"""Text platform for TCP gateway configuration fields."""

from inepro_metering.gateway_settings import (
    GatewaySettingDescription,
    get_gateway_settings,
)

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .gateway_support import IneproGatewayEntity, entry_supports_gateway_management


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TCP gateway text entities from a config entry."""
    del hass
    if not entry_supports_gateway_management(entry):
        return

    coordinator = entry.runtime_data
    async_add_entities(
        [
            IneproGatewayText(coordinator, entry, setting)
            for setting in get_gateway_settings(entity_platform="text")
        ]
    )


class IneproGatewayText(
    IneproGatewayEntity,
    TextEntity,
):
    """Expose one shared-library gateway text setting."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        setting: GatewaySettingDescription,
    ) -> None:
        """Initialize the gateway text entity."""
        super().__init__(coordinator, entry)
        self._setting = setting
        self._optimistic_value: str | None = None
        self._attr_name = setting.name
        self._attr_unique_id = f"{entry.entry_id}_gateway_{setting.key}_text"

    @property
    def native_value(self) -> str | None:
        """Return the current gateway text value."""
        actual_value: str | None = None
        state = self.gateway_setting_state(self._setting.key)
        if state is not None and isinstance(state.value, str):
            actual_value = state.value

        if actual_value is not None and self._optimistic_value == actual_value:
            self._optimistic_value = None

        return (
            self._optimistic_value
            if self._optimistic_value is not None
            else actual_value
        )

    async def async_set_value(self, value: str) -> None:
        """Write a new text value back to the gateway."""
        normalized_value = str(self._setting.normalize_value(value))
        self._optimistic_value = normalized_value
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_gateway_setting(
                setting_key=self._setting.key,
                value=value,
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise
        self.async_write_ha_state()
