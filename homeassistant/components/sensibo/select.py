"""Number platform for Sensibo integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity

PARALLEL_UPDATES = 0


@dataclass
class SensiboSelectDescriptionMixin:
    """Mixin values for Sensibo entities."""

    remote_key: str
    remote_options: str


@dataclass
class SensiboSelectEntityDescription(
    SelectEntityDescription, SensiboSelectDescriptionMixin
):
    """Class describing Sensibo Number entities."""


DEVICE_SELECT_TYPES = (
    SensiboSelectEntityDescription(
        key="horizontalSwing",
        remote_key="horizontal_swing_mode",
        remote_options="horizontal_swing_modes",
        name="Horizontal swing",
        icon="mdi:air-conditioner",
    ),
    SensiboSelectEntityDescription(
        key="light",
        remote_key="light_mode",
        remote_options="light_modes",
        name="Light",
        icon="mdi:flashlight",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo number platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboSelect(coordinator, device_id, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for description in DEVICE_SELECT_TYPES
        if description.key in device_data.full_features
    )


class SensiboSelect(SensiboDeviceBaseEntity, SelectEntity):
    """Representation of a Sensibo Select."""

    entity_description: SensiboSelectEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboSelectEntityDescription,
    ) -> None:
        """Initiate Sensibo Select."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        option: str | None = getattr(
            self.device_data, self.entity_description.remote_key
        )
        return option

    @property
    def options(self) -> list[str]:
        """Return possible options."""
        return getattr(self.device_data, self.entity_description.remote_options) or []

    async def async_select_option(self, option: str) -> None:
        """Set state to the selected option."""
        if self.entity_description.key not in self.device_data.active_features:
            raise HomeAssistantError(
                f"Current mode {self.device_data.hvac_mode} doesn't support setting {self.entity_description.name}"
            )

        params = {
            "name": self.entity_description.key,
            "value": option,
            "ac_states": self.device_data.ac_states,
            "assumed_state": False,
        }
        result = await self.async_send_command("set_ac_state", params)

        if result["result"]["status"] == "Success":
            setattr(self.device_data, self.entity_description.remote_key, option)
            self.async_write_ha_state()
            return

        failure = result["result"]["failureReason"]
        raise HomeAssistantError(
            f"Could not set state for device {self.name} due to reason {failure}"
        )
