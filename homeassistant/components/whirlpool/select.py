"""The select platform for Whirlpool Appliances."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, override

from whirlpool.appliance import Appliance
from whirlpool.oven import Cavity as OvenCavity, CookMode, Oven

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .const import DOMAIN
from .entity import WhirlpoolEntity, WhirlpoolOvenEntity

PARALLEL_UPDATES = 1

OVEN_COOK_MODES: Final[dict[CookMode, str]] = {
    CookMode.Standby: "standby",
    CookMode.Bake: "bake",
    CookMode.ConvectBake: "convection_bake",
    CookMode.Broil: "broil",
    CookMode.ConvectBroil: "convection_broil",
    CookMode.ConvectRoast: "convection_roast",
    CookMode.KeepWarm: "keep_warm",
    CookMode.AirFry: "air_fry",
}
OPTION_TO_OVEN_COOK_MODE: Final = {v: k for k, v in OVEN_COOK_MODES.items()}

# Target temperature (Celsius) used when a mode is selected while the oven is
# idle and has no target set yet.
DEFAULT_OVEN_TEMP = 175


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSelectDescription(SelectEntityDescription):
    """Class describing Whirlpool select entities."""

    value_fn: Callable[[Appliance], str | None]
    set_fn: Callable[[Appliance, str], Awaitable[bool]]


REFRIGERATOR_DESCRIPTIONS: Final[tuple[WhirlpoolSelectDescription, ...]] = (
    WhirlpoolSelectDescription(
        key="refrigerator_temperature_level",
        translation_key="refrigerator_temperature_level",
        options=["-4", "-2", "0", "3", "5"],
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda fridge: (
            str(val) if (val := fridge.get_offset_temp()) is not None else None
        ),
        set_fn=lambda fridge, option: fridge.set_offset_temp(int(option)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform."""
    appliances_manager = config_entry.runtime_data

    entities: list[SelectEntity] = [
        WhirlpoolSelectEntity(refrigerator, description)
        for refrigerator in appliances_manager.refrigerators
        for description in REFRIGERATOR_DESCRIPTIONS
    ]
    entities.extend(
        WhirlpoolOvenCookModeSelect(oven, cavity)
        for oven in appliances_manager.ovens
        for cavity in (OvenCavity.Upper, OvenCavity.Lower)
        if oven.get_oven_cavity_exists(cavity)
    )
    async_add_entities(entities)


class WhirlpoolSelectEntity(WhirlpoolEntity, SelectEntity):
    """Whirlpool select entity."""

    def __init__(
        self, appliance: Appliance, description: WhirlpoolSelectDescription
    ) -> None:
        """Initialize the select entity."""
        super().__init__(appliance, unique_id_suffix=f"-{description.key}")
        self.entity_description: WhirlpoolSelectDescription = description

    @override
    @property
    def current_option(self) -> str | None:
        """Retrieve currently selected option."""
        return self.entity_description.value_fn(self._appliance)

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        try:
            WhirlpoolSelectEntity._check_service_request(
                await self.entity_description.set_fn(self._appliance, option)
            )
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value_set",
            ) from err


class WhirlpoolOvenCookModeSelect(WhirlpoolOvenEntity, SelectEntity):
    """Settable cook mode for an oven cavity."""

    _attr_options = list(OVEN_COOK_MODES.values())

    def __init__(self, appliance: Oven, cavity: OvenCavity) -> None:
        """Initialize the oven cook mode select."""
        super().__init__(appliance, cavity, "oven_cook_mode", "-cook_mode")

    @override
    @property
    def current_option(self) -> str | None:
        """Return the current cook mode, if it is a selectable one."""
        return OVEN_COOK_MODES.get(self._appliance.get_cook_mode(self.cavity))

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the cook mode, keeping the current/last target temperature."""
        mode = OPTION_TO_OVEN_COOK_MODE[option]
        try:
            if mode == CookMode.Standby:
                # Standby is the idle state: the oven reaches it by cancelling
                # the current cook, not by starting a "standby" cook.
                result = await self._appliance.stop_cook(self.cavity)
            else:
                target = self._appliance.get_target_temp(self.cavity)
                if target is None:
                    target = DEFAULT_OVEN_TEMP
                result = await self._appliance.set_cook(
                    target_temp=target,
                    mode=mode,
                    cavity=self.cavity,
                )
            WhirlpoolOvenCookModeSelect._check_service_request(result)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value_set",
            ) from err
