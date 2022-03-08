"""Number platform for Sensibo integration."""
from __future__ import annotations


from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo number platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboSelect(coordinator, device_id)
        for device_id, device_data in coordinator.data.items()
        if device_data["hvac_modes"] and device_data["temp"]
    )


class SensiboSelect(SensiboBaseEntity, SelectEntity):
    """Representation of a Sensibo Select."""

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Sensibo Select."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}-horizontal_swing"
        self._attr_name = f"{coordinator.data[device_id]['name']} Horizontal Swing"

    @property
    def current_option(self) -> str | None:
        """Return the current selected live override."""
        return self.coordinator.data[self.unique_id]["horizontal_swing_modes"]

    @property
    def options(self) -> list[str]:
        return (
            self.coordinator.data[self.unique_id]["horizontal_swing_modes"]
            if self.coordinator.data[self.unique_id]["horizontal_swing_modes"]
            else None
        )

    async def async_select_option(self, option: str) -> None:
        """Set WLED state to the selected live override state."""
        if (
            "horizontalSwing"
            not in self.coordinator.data[self.unique_id]["active_features"]
        ):
            raise HomeAssistantError(
                "Current mode doesn't support setting horizontal swing"
            )

        params = {
            "name": "horizontalSwing",
            "value": option,
            "ac_states": self.coordinator.data[self.unique_id]["ac_states"],
            "assumed_state": False,
        }
        result = await self.async_send_command("set_ac_state", params)

        if result["result"]["status"] == "Success":
            self.coordinator.data[self.unique_id]["horizontal_swing_mode"] = option
            self.async_write_ha_state()
            return

        failure = result["result"]["failureReason"]
        raise HomeAssistantError(
            f"Could not set state for device {self.name} due to reason {failure}"
        )
