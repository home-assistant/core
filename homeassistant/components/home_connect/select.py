"""Provides a select platform for Home Connect."""

import contextlib
import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    HomeConnectConfigEntry,
    bsh_key_to_translation_key,
    get_dict_from_home_connect_error,
)
from .api import HomeConnectDevice
from .const import (
    APPLIANCES_WITH_PROGRAMS,
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    BSH_SELECTED_PROGRAM,
    DOMAIN,
    SVE_TRANSLATION_PLACEHOLDER_PROGRAM,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)

TRANSLATION_KEYS_PROGRAMS_MAP = {
    bsh_key_to_translation_key(program): program
    for program in (
        "ConsumerProducts.CleaningRobot.Program.Cleaning.CleanAll",
        "ConsumerProducts.CleaningRobot.Program.Cleaning.CleanMap",
        "ConsumerProducts.CleaningRobot.Program.Basic.GoHome",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Ristretto",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoDoppio",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Coffee",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.XLCoffee",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeGrande",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoMacchiato",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Cappuccino",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.LatteMacchiato",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeLatte",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.MilkFroth",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.WarmMilk",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.KleinerBrauner",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.GrosserBrauner",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Verlaengerter",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.VerlaengerterBraun",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.WienerMelange",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.FlatWhite",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Cortado",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeCortado",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeConLeche",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeAuLait",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Doppio",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Kaapi",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.KoffieVerkeerd",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Galao",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Garoto",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Americano",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.RedEye",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.BlackEye",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.DeadEye",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.HotWater",
        "Dishcare.Dishwasher.Program.PreRinse",
        "Dishcare.Dishwasher.Program.Auto1",
        "Dishcare.Dishwasher.Program.Auto2",
        "Dishcare.Dishwasher.Program.Auto3",
        "Dishcare.Dishwasher.Program.Eco50",
        "Dishcare.Dishwasher.Program.Quick45",
        "Dishcare.Dishwasher.Program.Intensiv70",
        "Dishcare.Dishwasher.Program.Normal65",
        "Dishcare.Dishwasher.Program.Glas40",
        "Dishcare.Dishwasher.Program.GlassCare",
        "Dishcare.Dishwasher.Program.NightWash",
        "Dishcare.Dishwasher.Program.Quick65",
        "Dishcare.Dishwasher.Program.Normal45",
        "Dishcare.Dishwasher.Program.Intensiv45",
        "Dishcare.Dishwasher.Program.AutoHalfLoad",
        "Dishcare.Dishwasher.Program.IntensivPower",
        "Dishcare.Dishwasher.Program.MagicDaily",
        "Dishcare.Dishwasher.Program.Super60",
        "Dishcare.Dishwasher.Program.Kurz60",
        "Dishcare.Dishwasher.Program.ExpressSparkle65",
        "Dishcare.Dishwasher.Program.MachineCare",
        "Dishcare.Dishwasher.Program.SteamFresh",
        "Dishcare.Dishwasher.Program.MaximumCleaning",
        "Dishcare.Dishwasher.Program.MixedLoad",
        "LaundryCare.Dryer.Program.Cotton",
        "LaundryCare.Dryer.Program.Synthetic",
        "LaundryCare.Dryer.Program.Mix",
        "LaundryCare.Dryer.Program.Blankets",
        "LaundryCare.Dryer.Program.BusinessShirts",
        "LaundryCare.Dryer.Program.DownFeathers",
        "LaundryCare.Dryer.Program.Hygiene",
        "LaundryCare.Dryer.Program.Jeans",
        "LaundryCare.Dryer.Program.Outdoor",
        "LaundryCare.Dryer.Program.SyntheticRefresh",
        "LaundryCare.Dryer.Program.Towels",
        "LaundryCare.Dryer.Program.Delicates",
        "LaundryCare.Dryer.Program.Super40",
        "LaundryCare.Dryer.Program.Shirts15",
        "LaundryCare.Dryer.Program.Pillow",
        "LaundryCare.Dryer.Program.AntiShrink",
        "LaundryCare.Dryer.Program.MyTime.MyDryingTime",
        "LaundryCare.Dryer.Program.TimeCold",
        "LaundryCare.Dryer.Program.TimeWarm",
        "LaundryCare.Dryer.Program.InBasket",
        "LaundryCare.Dryer.Program.TimeColdFix.TimeCold20",
        "LaundryCare.Dryer.Program.TimeColdFix.TimeCold30",
        "LaundryCare.Dryer.Program.TimeColdFix.TimeCold60",
        "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm30",
        "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm40",
        "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm60",
        "LaundryCare.Dryer.Program.Dessous",
        "Cooking.Common.Program.Hood.Automatic",
        "Cooking.Common.Program.Hood.Venting",
        "Cooking.Common.Program.Hood.DelayedShutOff",
        "Cooking.Oven.Program.HeatingMode.PreHeating",
        "Cooking.Oven.Program.HeatingMode.HotAir",
        "Cooking.Oven.Program.HeatingMode.HotAirEco",
        "Cooking.Oven.Program.HeatingMode.HotAirGrilling",
        "Cooking.Oven.Program.HeatingMode.TopBottomHeating",
        "Cooking.Oven.Program.HeatingMode.TopBottomHeatingEco",
        "Cooking.Oven.Program.HeatingMode.BottomHeating",
        "Cooking.Oven.Program.HeatingMode.PizzaSetting",
        "Cooking.Oven.Program.HeatingMode.SlowCook",
        "Cooking.Oven.Program.HeatingMode.IntensiveHeat",
        "Cooking.Oven.Program.HeatingMode.KeepWarm",
        "Cooking.Oven.Program.HeatingMode.PreheatOvenware",
        "Cooking.Oven.Program.HeatingMode.FrozenHeatupSpecial",
        "Cooking.Oven.Program.HeatingMode.Desiccation",
        "Cooking.Oven.Program.HeatingMode.Defrost",
        "Cooking.Oven.Program.HeatingMode.Proof",
        "Cooking.Oven.Program.HeatingMode.HotAir30Steam",
        "Cooking.Oven.Program.HeatingMode.HotAir60Steam",
        "Cooking.Oven.Program.HeatingMode.HotAir80Steam",
        "Cooking.Oven.Program.HeatingMode.HotAir100Steam",
        "Cooking.Oven.Program.HeatingMode.SabbathProgramme",
        "Cooking.Oven.Program.Microwave.90Watt",
        "Cooking.Oven.Program.Microwave.180Watt",
        "Cooking.Oven.Program.Microwave.360Watt",
        "Cooking.Oven.Program.Microwave.600Watt",
        "Cooking.Oven.Program.Microwave.900Watt",
        "Cooking.Oven.Program.Microwave.1000Watt",
        "Cooking.Oven.Program.Microwave.Max",
        "Cooking.Oven.Program.HeatingMode.WarmingDrawer",
        "LaundryCare.Washer.Program.Cotton",
        "LaundryCare.Washer.Program.Cotton.CottonEco",
        "LaundryCare.Washer.Program.Cotton.Eco4060",
        "LaundryCare.Washer.Program.Cotton.Colour",
        "LaundryCare.Washer.Program.EasyCare",
        "LaundryCare.Washer.Program.Mix",
        "LaundryCare.Washer.Program.Mix.NightWash",
        "LaundryCare.Washer.Program.DelicatesSilk",
        "LaundryCare.Washer.Program.Wool",
        "LaundryCare.Washer.Program.Sensitive",
        "LaundryCare.Washer.Program.Auto30",
        "LaundryCare.Washer.Program.Auto40",
        "LaundryCare.Washer.Program.Auto60",
        "LaundryCare.Washer.Program.Chiffon",
        "LaundryCare.Washer.Program.Curtains",
        "LaundryCare.Washer.Program.DarkWash",
        "LaundryCare.Washer.Program.Dessous",
        "LaundryCare.Washer.Program.Monsoon",
        "LaundryCare.Washer.Program.Outdoor",
        "LaundryCare.Washer.Program.PlushToy",
        "LaundryCare.Washer.Program.ShirtsBlouses",
        "LaundryCare.Washer.Program.SportFitness",
        "LaundryCare.Washer.Program.Towels",
        "LaundryCare.Washer.Program.WaterProof",
        "LaundryCare.Washer.Program.PowerSpeed59",
        "LaundryCare.Washer.Program.Super153045.Super15",
        "LaundryCare.Washer.Program.Super153045.Super1530",
        "LaundryCare.Washer.Program.DownDuvet.Duvet",
        "LaundryCare.Washer.Program.Rinse.RinseSpinDrain",
        "LaundryCare.Washer.Program.DrumClean",
        "LaundryCare.WasherDryer.Program.Cotton",
        "LaundryCare.WasherDryer.Program.Cotton.Eco4060",
        "LaundryCare.WasherDryer.Program.Mix",
        "LaundryCare.WasherDryer.Program.EasyCare",
        "LaundryCare.WasherDryer.Program.WashAndDry60",
        "LaundryCare.WasherDryer.Program.WashAndDry90",
    )
}

PROGRAMS_TRANSLATION_KEYS_MAP = {
    value: key for key, value in TRANSLATION_KEYS_PROGRAMS_MAP.items()
}

PROGRAM_SELECT_ENTITY_DESCRIPTIONS = (
    SelectEntityDescription(
        key=BSH_ACTIVE_PROGRAM,
        translation_key="active_program",
    ),
    SelectEntityDescription(
        key=BSH_SELECTED_PROGRAM,
        translation_key="selected_program",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""

    def get_entities() -> list[HomeConnectProgramSelectEntity]:
        """Get a list of entities."""
        entities: list[HomeConnectProgramSelectEntity] = []
        programs_not_found = set()
        for device in entry.runtime_data.devices:
            if device.appliance.type in APPLIANCES_WITH_PROGRAMS:
                with contextlib.suppress(HomeConnectError):
                    programs = device.appliance.get_programs_available()
                    if programs:
                        for program in programs.copy():
                            if program not in PROGRAMS_TRANSLATION_KEYS_MAP:
                                programs.remove(program)
                                if program not in programs_not_found:
                                    _LOGGER.info(
                                        'The program "%s" is not part of the official Home Connect API specification',
                                        program,
                                    )
                                    programs_not_found.add(program)
                        entities.extend(
                            HomeConnectProgramSelectEntity(device, programs, desc)
                            for desc in PROGRAM_SELECT_ENTITY_DESCRIPTIONS
                        )
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    """Select class for Home Connect programs."""

    def __init__(
        self,
        device: HomeConnectDevice,
        programs: list[str],
        desc: SelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            device,
            desc,
        )
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS_MAP[program] for program in programs
        ]
        self.start_on_select = desc.key == BSH_ACTIVE_PROGRAM

    async def async_update(self) -> None:
        """Update the program selection status."""
        program = self.device.appliance.status.get(self.bsh_key, {}).get(ATTR_VALUE)
        if not program:
            program_translation_key = None
        elif not (
            program_translation_key := PROGRAMS_TRANSLATION_KEYS_MAP.get(program)
        ):
            _LOGGER.debug(
                'The program "%s" is not part of the official Home Connect API specification',
                program,
            )
        self._attr_current_option = program_translation_key
        _LOGGER.debug("Updated, new program: %s", self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        bsh_key = TRANSLATION_KEYS_PROGRAMS_MAP[option]
        _LOGGER.debug(
            "Starting program: %s" if self.start_on_select else "Selecting program: %s",
            bsh_key,
        )
        if self.start_on_select:
            target = self.device.appliance.start_program
        else:
            target = self.device.appliance.select_program
        try:
            await self.hass.async_add_executor_job(target, bsh_key)
        except HomeConnectError as err:
            if self.start_on_select:
                translation_key = "start_program"
            else:
                translation_key = "select_program"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_PROGRAM: bsh_key,
                },
            ) from err
        self.async_entity_update()
