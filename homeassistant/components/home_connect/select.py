"""Provides a selector for Home Connect."""

import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ConfigEntryAuth, HomeConnectDevice
from .const import ATTR_VALUE, BSH_ACTIVE_PROGRAM, DOMAIN
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)

PROGRAMS_TRANSLATION_KEYS = {
    "ConsumerProducts.CleaningRobot.Program.Cleaning.CleanAll": "clean_all",
    "ConsumerProducts.CleaningRobot.Program.Cleaning.CleanMap": "clean_map",
    "ConsumerProducts.CleaningRobot.Program.Basic.GoHome": "go_home",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.Ristretto": "ristretto",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso": "espresso",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoDoppio": "espresso_doppio",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.Coffee": "coffee",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.XLCoffee": "x_l_coffee",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeGrande": "caffe_grande",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoMacchiato": "espresso_macchiato",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.Cappuccino": "cappuccino",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.LatteMacchiato": "latte_macchiato",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeLatte": "caffe_latte",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.MilkFroth": "milk_froth",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.WarmMilk": "warm_milk",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.KleinerBrauner": "kleiner_brauner",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.GrosserBrauner": "grosser_brauner",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Verlaengerter": "verlaengerter",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.VerlaengerterBraun": "verlaengerter_braun",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.WienerMelange": "wiener_melange",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.FlatWhite": "flat_white",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Cortado": "cortado",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeCortado": "cafe_cortado",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeConLeche": "cafe_con_leche",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeAuLait": "cafe_au_lait",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Doppio": "doppio",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Kaapi": "kaapi",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.KoffieVerkeerd": "koffie_verkeerd",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Galao": "galao",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Garoto": "garoto",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Americano": "americano",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.RedEye": "red_eye",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.BlackEye": "black_eye",
    "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.DeadEye": "dead_eye",
    "ConsumerProducts.CoffeeMaker.Program.Beverage.HotWater": "hot_water",
    "Dishcare.Dishwasher.Program.PreRinse": "pre_rinse",
    "Dishcare.Dishwasher.Program.Auto1": "auto1",
    "Dishcare.Dishwasher.Program.Auto2": "auto2",
    "Dishcare.Dishwasher.Program.Auto3": "auto3",
    "Dishcare.Dishwasher.Program.Eco50": "eco50",
    "Dishcare.Dishwasher.Program.Quick45": "quick45",
    "Dishcare.Dishwasher.Program.Intensiv70": "intensiv70",
    "Dishcare.Dishwasher.Program.Normal65": "normal65",
    "Dishcare.Dishwasher.Program.Glas40": "glas40",
    "Dishcare.Dishwasher.Program.GlassCare": "glass_care",
    "Dishcare.Dishwasher.Program.NightWash": "night_wash",
    "Dishcare.Dishwasher.Program.Quick65": "quick65",
    "Dishcare.Dishwasher.Program.Normal45": "normal45",
    "Dishcare.Dishwasher.Program.Intensiv45": "intensiv45",
    "Dishcare.Dishwasher.Program.AutoHalfLoad": "auto_half_load",
    "Dishcare.Dishwasher.Program.IntensivPower": "intensiv_power",
    "Dishcare.Dishwasher.Program.MagicDaily": "magic_daily",
    "Dishcare.Dishwasher.Program.Super60": "super60",
    "Dishcare.Dishwasher.Program.Kurz60": "kurz60",
    "Dishcare.Dishwasher.Program.ExpressSparkle65": "express_sparkle65",
    "Dishcare.Dishwasher.Program.MachineCare": "machine_care",
    "Dishcare.Dishwasher.Program.SteamFresh": "steam_fresh",
    "Dishcare.Dishwasher.Program.MaximumCleaning": "maximum_cleaning",
    "Dishcare.Dishwasher.Program.MixedLoad": "mixed_load",
    "LaundryCare.Dryer.Program.Cotton": "cotton",
    "LaundryCare.Dryer.Program.Synthetic": "synthetic",
    "LaundryCare.Dryer.Program.Mix": "mix",
    "LaundryCare.Dryer.Program.Blankets": "blankets",
    "LaundryCare.Dryer.Program.BusinessShirts": "business_shirts",
    "LaundryCare.Dryer.Program.DownFeathers": "down_feathers",
    "LaundryCare.Dryer.Program.Hygiene": "hygiene",
    "LaundryCare.Dryer.Program.Jeans": "jeans",
    "LaundryCare.Dryer.Program.Outdoor": "outdoor",
    "LaundryCare.Dryer.Program.SyntheticRefresh": "synthetic_refresh",
    "LaundryCare.Dryer.Program.Towels": "towels",
    "LaundryCare.Dryer.Program.Delicates": "delicates",
    "LaundryCare.Dryer.Program.Super40": "super40",
    "LaundryCare.Dryer.Program.Shirts15": "shirts15",
    "LaundryCare.Dryer.Program.Pillow": "pillow",
    "LaundryCare.Dryer.Program.AntiShrink": "anti_shrink",
    "LaundryCare.Dryer.Program.MyTime.MyDryingTime": "my_drying_time",
    "LaundryCare.Dryer.Program.TimeCold": "cold",
    "LaundryCare.Dryer.Program.TimeWarm": "warm",
    "LaundryCare.Dryer.Program.InBasket": "in_basket",
    "LaundryCare.Dryer.Program.TimeColdFix.TimeCold20": "cold20",
    "LaundryCare.Dryer.Program.TimeColdFix.TimeCold30": "cold30",
    "LaundryCare.Dryer.Program.TimeColdFix.TimeCold60": "cold60",
    "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm30": "warm30",
    "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm40": "warm40",
    "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm60": "warm60",
    "LaundryCare.Dryer.Program.Dessous": "dessous",
    "Cooking.Common.Program.Hood.Automatic": "automatic",
    "Cooking.Common.Program.Hood.Venting": "venting",
    "Cooking.Common.Program.Hood.DelayedShutOff": "delayed_shut_off",
    "Cooking.Oven.Program.HeatingMode.PreHeating": "pre_heating",
    "Cooking.Oven.Program.HeatingMode.HotAir": "hot_air",
    "Cooking.Oven.Program.HeatingMode.HotAirEco": "hot_air_eco",
    "Cooking.Oven.Program.HeatingMode.HotAirGrilling": "hot_air_grilling",
    "Cooking.Oven.Program.HeatingMode.TopBottomHeating": "top_bottom_heating",
    "Cooking.Oven.Program.HeatingMode.TopBottomHeatingEco": "top_bottom_heating_eco",
    "Cooking.Oven.Program.HeatingMode.BottomHeating": "bottom_heating",
    "Cooking.Oven.Program.HeatingMode.PizzaSetting": "pizza_setting",
    "Cooking.Oven.Program.HeatingMode.SlowCook": "slow_cook",
    "Cooking.Oven.Program.HeatingMode.IntensiveHeat": "intensive_heat",
    "Cooking.Oven.Program.HeatingMode.KeepWarm": "keep_warm",
    "Cooking.Oven.Program.HeatingMode.PreheatOvenware": "preheat_ovenware",
    "Cooking.Oven.Program.HeatingMode.FrozenHeatupSpecial": "frozen_heatup_special",
    "Cooking.Oven.Program.HeatingMode.Desiccation": "desiccation",
    "Cooking.Oven.Program.HeatingMode.Defrost": "defrost",
    "Cooking.Oven.Program.HeatingMode.Proof": "proof",
    "Cooking.Oven.Program.HeatingMode.HotAir30Steam": "hot_air30_steam",
    "Cooking.Oven.Program.HeatingMode.HotAir60Steam": "hot_air60_steam",
    "Cooking.Oven.Program.HeatingMode.HotAir80Steam": "hot_air80_steam",
    "Cooking.Oven.Program.HeatingMode.HotAir100Steam": "hot_air100_steam",
    "Cooking.Oven.Program.HeatingMode.SabbathProgramme": "sabbath_programme",
    "Cooking.Oven.Program.Microwave.90Watt": "90_watt",
    "Cooking.Oven.Program.Microwave.180Watt": "180_watt",
    "Cooking.Oven.Program.Microwave.360Watt": "360_watt",
    "Cooking.Oven.Program.Microwave.600Watt": "600_watt",
    "Cooking.Oven.Program.Microwave.900Watt": "900_watt",
    "Cooking.Oven.Program.Microwave.1000Watt": "1000_watt",
    "Cooking.Oven.Program.Microwave.Max": "max",
    "Cooking.Oven.Program.HeatingMode.WarmingDrawer": "warming_drawer",
    "LaundryCare.Washer.Program.Cotton": "cotton",
    "LaundryCare.Washer.Program.Cotton.CottonEco": "cotton_eco",
    "LaundryCare.Washer.Program.Cotton.Eco4060": "cotton_eco4060",
    "LaundryCare.Washer.Program.Cotton.Colour": "cotton_colour",
    "LaundryCare.Washer.Program.EasyCare": "easy_care",
    "LaundryCare.Washer.Program.Mix": "mix",
    "LaundryCare.Washer.Program.Mix.NightWash": "mix_night_wash",
    "LaundryCare.Washer.Program.DelicatesSilk": "delicates_silk",
    "LaundryCare.Washer.Program.Wool": "wool",
    "LaundryCare.Washer.Program.Sensitive": "sensitive",
    "LaundryCare.Washer.Program.Auto30": "auto30",
    "LaundryCare.Washer.Program.Auto40": "auto40",
    "LaundryCare.Washer.Program.Auto60": "auto60",
    "LaundryCare.Washer.Program.Chiffon": "chiffon",
    "LaundryCare.Washer.Program.Curtains": "curtains",
    "LaundryCare.Washer.Program.DarkWash": "dark_wash",
    "LaundryCare.Washer.Program.Dessous": "dessous",
    "LaundryCare.Washer.Program.Monsoon": "monsoon",
    "LaundryCare.Washer.Program.Outdoor": "outdoor",
    "LaundryCare.Washer.Program.PlushToy": "plush_toy",
    "LaundryCare.Washer.Program.ShirtsBlouses": "shirts_blouses",
    "LaundryCare.Washer.Program.SportFitness": "sport_fitness",
    "LaundryCare.Washer.Program.Towels": "towels",
    "LaundryCare.Washer.Program.WaterProof": "water_proof",
    "LaundryCare.Washer.Program.PowerSpeed59": "power_speed59",
    "LaundryCare.Washer.Program.Super153045.Super15": "super15",
    "LaundryCare.Washer.Program.Super153045.Super1530": "super1530",
    "LaundryCare.Washer.Program.DownDuvet.Duvet": "duvet",
    "LaundryCare.Washer.Program.Rinse.RinseSpinDrain": "rinse_spin_drain",
    "LaundryCare.Washer.Program.DrumClean": "drum_clean",
    "LaundryCare.WasherDryer.Program.Cotton": "cotton",
    "LaundryCare.WasherDryer.Program.Cotton.Eco4060": "cotton_eco4060",
    "LaundryCare.WasherDryer.Program.Mix": "mix",
    "LaundryCare.WasherDryer.Program.EasyCare": "easy_care",
    "LaundryCare.WasherDryer.Program.WashAndDry.60": "wash_and_dry_60",
    "LaundryCare.WasherDryer.Program.WashAndDry.90": "wash_and_dry_90",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            select_entity = device_dict.get(CONF_ENTITIES, {}).get("select", None)
            if select_entity is None:
                continue
            entities += [HomeConnectProgramSelectEntity(**select_entity)]
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    "Select class for Home Connect."

    _attr_has_entity_name = True
    translation_key_to_bsh_key_map: dict[str, str]

    def __init__(self, device: HomeConnectDevice, programs: list[str]) -> None:
        """Initialize the entity."""
        super().__init__(device, "program", "")
        del self._attr_name
        self._attr_translation_key = "program"
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS[program] for program in programs
        ]
        self.translation_key_to_bsh_key_map = {
            PROGRAMS_TRANSLATION_KEYS[program]: program for program in programs
        }

    async def async_update(self) -> None:
        """Update the program selection status."""
        bsh_key_option = self.device.appliance.status.get(BSH_ACTIVE_PROGRAM, {}).get(
            ATTR_VALUE
        )
        self._attr_current_option = PROGRAMS_TRANSLATION_KEYS.get(bsh_key_option)
        _LOGGER.debug("Updated, new program: %s", bsh_key_option)

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        bsh_key_option = self.translation_key_to_bsh_key_map[option]
        _LOGGER.debug("Tried to select program: %s", bsh_key_option)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.start_program, bsh_key_option
            )
        except HomeConnectError as err:
            _LOGGER.error(
                "Error while trying to select program %s: %s", bsh_key_option, err
            )
        self.async_entity_update()
