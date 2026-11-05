"""Select platform for aerosmart."""

from dataclasses import dataclass
from typing import cast, override

from aerosmart_modbus.enums import VentilationMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AerosmartConfigEntry
from .entity import AerosmartEntity, AerosmartEntityDescription

PARALLEL_UPDATES = 0

VENTILATION_MODE_TO_OPTION = {
    VentilationMode.MANUAL_0: "manual_0",
    VentilationMode.MANUAL_1: "manual_1",
    VentilationMode.MANUAL_2: "manual_2",
    VentilationMode.MANUAL_3: "manual_3",
    VentilationMode.AUTOMATIC: "automatic",
    VentilationMode.PARTY: "party",
}
OPTION_TO_VENTILATION_MODE = {
    option: mode for mode, option in VENTILATION_MODE_TO_OPTION.items()
}


@dataclass(frozen=True, kw_only=True)
class AerosmartSelectEntityDescription(
    SelectEntityDescription, AerosmartEntityDescription
):
    """Describe an aerosmart select entity."""


SELECT_DESCRIPTION = AerosmartSelectEntityDescription(
    key="ventilation_mode",
    translation_key="ventilation_mode",
    component="ventilation",
    attribute="betriebsart",
    options=list(OPTION_TO_VENTILATION_MODE),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AerosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the aerosmart select entity."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            AerosmartVentilationModeSelect(
                runtime.coordinator_for("ventilation"),
                SELECT_DESCRIPTION,
            )
        ]
    )


class AerosmartVentilationModeSelect(AerosmartEntity, SelectEntity):
    """Represent the aerosmart ventilation operating mode."""

    entity_description: AerosmartSelectEntityDescription

    @property
    @override
    def current_option(self) -> str | None:
        """Return the confirmed ventilation mode."""
        mode = cast(
            "VentilationMode | None", self.coordinator.device.ventilation.betriebsart
        )
        if mode is None:
            return None
        return VENTILATION_MODE_TO_OPTION[mode]

    @override
    async def async_select_option(self, option: str) -> None:
        """Set and confirm the ventilation mode."""
        await self._async_write_verified(OPTION_TO_VENTILATION_MODE[option])
