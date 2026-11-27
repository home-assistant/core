"""Select entity for Electrolux Integration."""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Concatenate, override

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.dh_appliance import DHAppliance
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.hb_appliance import HBAppliance
from electrolux_group_developer_sdk.client.appliances.hd_appliance import HDAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance
from electrolux_group_developer_sdk.constants import (
    APPLIANCE_STATE_IDLE,
    APPLIANCE_STATE_READY_TO_START,
    APPLIANCE_STATE_RUNNING,
    RC_ENABLED,
    RC_NOT_SAFETY_RELEVANT_ENABLED,
)
from electrolux_group_developer_sdk.feature_constants import (
    FAN_SPEED,
    HOOD_FAN_LEVEL,
    HOOD_FAN_SPEED,
    HOOD_STATE,
    KEY_SOUND_TONE,
    PROGRAM,
    PROGRAM_CAPABILITY,
    SPIN_SPEED_CAPABILITY,
    TEMPERATURE_CAPABILITY,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import convert_to_snake_case

_LOGGER = logging.getLogger(__name__)

OVEN_PROGRAM_TO_HA_OPTION: dict[str, str] = {
    "AUGRATIN": "augratin",
    "BOTTOM": "bottom",
    "BREAD_BAKING": "bread_baking",
    "CONVENTIONAL_COOKING": "conventional_cooking",
    "BOTTOM_GRILL": "conventional_cooking",
    "DEFROST": "defrost",
    "DEHYDRATE": "dehydrate",
    "DIRECT_STEAM": "steam_bake",
    "STEAM_DIRECT": "steam_bake",
    "DOUGH_PROVING": "dough_proofing",
    "DRYING": "dehydrate",
    "FROZEN_FOOD": "frozen_foods",
    "BOTTOM_GRILL_FAN": "frozen_foods",
    "FULL_STEAM": "full_steam",
    "GRILL": "grill",
    "GRILL_FAN": "turbo_grill",
    "HUMIDITY_HIGH": "steam_high",
    "HUMIDITY_LOW": "steam_low",
    "HUMIDITY_MEDIUM": "steam_medium",
    "KEEP_WARM": "keep_warm",
    "LOW_STEAM": "steam_low",
    "MOIST_FAN_BAKING": "moist_fan_bake",
    "MOIST_FAN_BAKE": "moist_fan_bake",
    "PASTA_STEAMED": "pasta",
    "PIZZA": "pizza",
    "PIZZA_FROZEN": "pizza_frozen",
    "PIZZA_WARM_UP": "pizza_warm_up",
    "STONE_BAKED_PIZZA": "pizza_stone_baked",
    "CAULIFLOWER_PIZZA": "pizza_cauliflower",
    "GLUTENFREE_PIZZA": "pizza_glutenfree",
    "CALZONE": "calzone",
    "NA_PITA": "pita_bread",
    "NA_NAAN": "naan",
    "NA_MATZAH": "matzah",
    "SLOW_COOKER": "slow_cooking",
    "BOTTOM_TRUE_FAN": "pizza",
    "PLATE_WARMING": "plate_warming",
    "PRESERVING": "preserving",
    "REGENERATE": "steam_regenerating",
    "SOUS_VIDE": "sous_vide",
    "STEAM_REGENERATING": "steam_regenerating",
    "TRUE_FAN": "true_fan",
    "TURBO_GRILL": "turbo_grill",
    "YOGHURT": "yoghurt",
    "STEAM_FRY": "steamify",
    "STEAMIFY": "steamify",
    "CLEAN_DESCALING": "descaling",
    "CLEAN_DRYING": "drying",
    "STEAM_CLEAN_DRY": "drying",
    "STEAM_SYSTEM_CLEAN_DRY": "drying",
    "STEAM_CLEAN_DESCALE": "descaling",
    "STEAM_CLEAN_INTENSE": "steam_clean_plus",
    "STEAM_CLEAN_LIGHT": "steam_clean",
    "STEAM_CLEAN_RINSING": "rinsing",
    "STEAM_CLEAN_RINSE": "rinsing",
    "STEAM_SYSTEM_CLEAN_RINSE": "rinsing",
    "STEAM_CLEAN_TANK_EMPTY": "tank_empty",
    "STEAM_SYSTEM_CLEAN_TANK_EMPTY": "tank_empty",
    "PYRO_CLEAN_LIGHT": "pyro_clean_quick",
    "PYRO_CLEAN_NORMAL": "pyro_clean_normal",
    "PYRO_CLEAN_INTENSE": "pyro_clean_intense",
    "AIR_FRY": "air_fry",
    "BAKE": "bake",
    "BAKE_BROIL": "top_bottom",
    "BAKE_BROIL_FAN": "hot_air_top_bottom",
    "BAKE_TRUE_FAN": "hot_air_bottom",
    "BAKE_TRUE_FAN_STEAM": "hot_air_bottom_steam",
    "BREAD_PROOF": "dough_proofing",
    "CONVENTIONAL_BAKE": "conventional_bake",
    "CONVENTIONAL_ROAST": "conventional_roast",
    "PRE_HEAT": "no_preheat",
    "MULTI_RACK_COOKING": "multi_rack",
    "TURKEY": "turkey",
    "BROIL": "broil",
    "BROIL_FAN": "hot_air_top",
    "STEAM_ROAST": "steam_roast",
    "STEAM_BAKE": "steam_bake",
    "DIRECT_STEAM_STEAM_BAKE": "steam_bake",
    "STEAM_CLEAN": "steam_clean",
    "SELF_CLEAN": "self_clean",
    "SLOW_COOKING": "slow_cooking",
    "DOUGH_PROOFING": "dough_proofing",
    "MEAT_AND_FISH_STEAMED": "meat_and_fish",
    "PASTA_AND_PIZZA_STEAMED": "pasta_and_pizza",
    "BREAD_STEAMED": "bread_baking",
    "PIES_AND_CAKES_STEAMED": "pies",
    "VEGETABLES_STEAMED": "vegetables",
    "POTATO_NATURA_AIRFRY": "rustic_potatoes",
    "NUGGETS_AIRFRY": "nuggets_and_chicken_wings",
    "CHEESE_BREAD_AIRFRY": "cheese_bread",
    "FROZEN_FRENCH_FRIES_AIRFRY": "frozen_french_fries",
    "CHIPS_AIRFRY": "chips",
    "AIR_SOUS_VIDE": "air_sous_vide",
    "WATER_BATH": "water_bath",
    "ASSIST_DIRECT_STEAM_ROAST_BEEF_RARE": "steam_meat",
    "STEAM_MEAT": "steam_meat",
    "MANUAL_AIRFRY": "manual",
    "MICROWAVE_BAKE_BROIL": "microwave_conventional_cooking",
    "MICROWAVE_BROIL": "microwave_grill",
    "MICROWAVE_GRILL": "microwave_grill",
    "MICROWAVE_BROIL_FAN": "microwave_turbo_grill",
    "MICROWAVE_PURE_FULL": "microwave",
    "MICROWAVE_TRUE_FAN": "microwave_true_fan",
    "DIRECT_STEAM_BREAD_BAKING": "bread_baking",
    "DIRECT_STEAM_REGENERATE": "steam_regenerating",
    "CATA_CLEAN_NORMAL": "catalytic_cleaning",
    "STEAM_LOW": "steam_low",
    "STEAM_MEDIUM": "steam_medium",
    "STEAM_HIGH": "steam_high",
    "TWO_TIMER_PROGRAM_SOUS_VIDE_NORMAL": "precision_steam",
    "PRO_STEAM": "pro_steam",
}

HOOD_FAN_SPEED_TO_HA_OPTION: dict[str, str] = {
    "AUTO": "auto",
    "BOOST": "boost",
    "BOOST_2": "intensive",
    "BREEZE": "breeze",
    "OFF": "off",
    "STEP_1": "low",
    "STEP_2": "medium",
    "STEP_3": "high",
}

DEHUMIDIFIER_FAN_SPEED_TO_HA_OPTION: dict[str, str] = {
    "AUTO": "auto",
    "TURBO": "turbo",
    "QUIET": "quiet",
    "LOW": "low",
    "MIDDLE": "medium",
    "HIGH": "high",
}

CARE_PROGRAM_TO_HA_OPTION: dict[str, str] = {
    "EXPRESS_PR_ABSOLUTEWASH49MIN": "absolute_wash",
    "AUTO": "auto",
    "AUTO_EASY_IRON_PR_EASYIRON_TD": "easy_iron",
    "BABY_PR_BABY": "baby_clothes",
    "BABY_PR_BABYCARE": "baby_clothes",
    "BABY_PR_BABY_WM_WD": "baby_clothes",
    "BED_LINEN_PLUS_PR_BEDLINENPLUSITA": "bed_linen_xl",
    "BED_LINEN_PLUS_PR_BEDDINGPLUS": "bed_linen_xl",
    "BEDLINEN_XL_PR_BEDLINENXL": "bed_linen_xl",
    "BLANKET_PR_PILLOWS": "pillow",
    "BLANKET_PR_DUVET": "duvet",
    "BLANKET_PR_BEDDING": "duvet",
    "COTTON_PR_COTTONS": "cotton",
    "COTTON_PR_COLOURPRO": "color_pro",
    "COTTON_PR_COTTONECO": "cotton_eco",
    "COTTON_PR_ENERGY_SAVER": "cotton_eco",
    "COTTON_PR_ENERGYSAVER": "cotton_eco",
    "COTTON_PR_BUSINESSSHIRTS": "business_shirt",
    "COTTON_PR_ECO40-60": "eco_40_60_degrees",
    "COTTON_PR_ECO_COTTONS": "cotton_eco",
    "COTTON_PR_TOWELS": "towels",
    "COTTON_PR_WORKINGCLOTHES": "workwear",
    "CURTAINS_PR_CURTAINS": "curtains",
    "DELICATE_PR_CURTAINS": "curtains",
    "DELICATE_PR_DELICATES": "delicates",
    "DELICATE_PR_BABYCARE": "baby_clothes",
    "DELICATE_PR_SOFTTOYS": "soft_toys",
    "DELICATE_PR_DELICATEPLUS": "delicates_plus",
    "DELICATE_PR_BABY": "baby_clothes",
    "EXTRA_DELICATE_PR_DELICATES": "delicates",
    "DELICATE_SPORT": "delicate_sport",
    "JEANS_PR_DENIM": "denim",
    "DENIM_PR_DENIM": "denim",
    "DRAIN_PR_DRAIN": "drain",
    "DRUM_CLEAN_PR_DRUM_CLEAN": "machine_clean",
    "DRUM_CLEAN_PR_MACHINECLEAN": "machine_clean",
    "DRUM_CLEAN_PR_TUB_CLEAN": "machine_clean",
    "TIMEDRY_PR_DRYINGRACK": "drying_rack",
    "DUVET_PR_DUVET": "duvet",
    "STEAM_DEWRINKLER_PR_DUVETCARE60": "duvet_care",
    "DUVET_PR_HYGENIC": "hygiene",
    "DUVET_PR_HYGENICCARE": "hygiene",
    "AUTO_EASY_IRON_PR_EASYIRON": "easy_iron",
    "ECO": "eco",
    "EXPRESS_PR_MYWASH49MIN": "my_wash",
    "EXPRESS_PR_EXPRESSCARE49MIN": "my_wash",
    "EXPRESS_PR_ULTRAWASH59MIN": "ultra_wash",
    "EXPRESS_PR_OKOPOWER": "oko_power",
    "EXPRESS_PR_OKOPOWER59MIN": "oko_power",
    "EXPRESS_PR_DAILY_60": "daily_60",
    "EXPRESS_PR_BUSINESSSHIRT": "business_shirt",
    "EXPRESS_PR_FULLWASH60": "full_wash_60",
    "EXPRESS_PR_MIXLOAD": "mix_load",
    "EXPRESS_PR_MIXLOAD69MIN": "mix_load",
    "EXPRESS_PR_POWERCLEAN": "power_clean",
    "EXPRESS_PR_POWERCLEAN59MIN": "power_clean_59min",
    "EXPRESS_PR_ULTRAWASH": "ultra_wash",
    "EXPRESS_PR_QUICK39MIN": "daily_39",
    "EXPRESS_PR_ULTRAQUICK39MIN": "ultra_quick_39",
    "EXPRESS_PR_ULTRAQUICK49MIN": "ultra_quick_49",
    "EXPRESS_PR_ULTRAQUICK59MIN": "ultra_quick_59",
    "FLEECE_PR_FLEECE": "fleece",
    "HEAVY": "heavy",
    "HYGIENE_PR_HYGIENE": "hygiene",
    "EXPRESS_PR_INTELLIQUICK": "intelliquick",
    "INTENSIVE": "intensive",
    "DOWN_JACKET_PR_DOWN_JACKET": "down_jackets",
    "JEANS_PR_JEANS": "jeans",
    "JEANS_PR_DARKCLOTHES": "dark_clothes",
    "LWI13_FAST": "quick",
    "LINEN_PR_LINEN": "linen",
    "LINEN_PR_LINEN_WM_WD": "linen",
    "120_MIN": "2_hours",
    "MACHINE_CARE": "machine_clean",
    "MINI_PR_SILK": "silk",
    "UNIVERSAL_PR_MIXEDPLUS": "mixed_xl",
    "MIXLOAD_PR_MIXED": "mixed_xl",
    "MY_DRY_PR_MIXCARE": "mix_care",
    "MY_DRY_PR_MYDRY": "my_dry",
    "MY_DRY_PR_MIXDRY": "mix_dry",
    "MY_DRY_PR_MIXED_DRY": "mix_dry",
    "NA_ALLERGEN_PR_ALLERGEN": "anti_allergy",
    "NON_STOP_3KG_3H_NONSTOP3H_3KG": "nonstop_3",
    "NON_STOP_3KG_3H_ONE_GO_3H_3KG": "nonstop_3",
    "NORMAL": "normal",
    "NORMAL90": "dish_normal",
    "ODERMATT_39_MIN": "odermatt",
    "ONE_ITEM_FAST_PR_1ITEMFAST": "1_item",
    "ONE_ITEM_FAST_PR_ONEITEMFAST": "1_item",
    "OUTD_PROOF_PR_OUTDOOR": "outdoor",
    "PETBED_PR_PETHAIR": "pet_hair",
    "PET_HAIR_PR_PETHAIR": "pet_hair",
    "PILLOWS_PR_PILLOW": "pillow",
    "OUTD_PROOF_PR_PROOFINGTREATMENT": "waterproof",
    "QUICK_20_MIN_PR_20MIN3KG": "20_min",
    "QUICK_20_MIN_PR_RAPID20MIN": "rapid_20_min",
    "QUICK30": "30_min",
    "QUICK60": "1_hour",
    "EXPRESS_PR_QUICKCARE49MIN": "quick_care_49",
    "EXPRESS_PR_QUICKCARE59MIN": "quick_care_59",
    "EXPRESS_PR_QUICKCARE69MIN": "quick_care_69",
    "QUICK_PR_FAST_3KG": "quick_3kg",
    "QUICK_PR_QUICK_3KG": "quick_3kg",
    "QUICK_WASH_DRY_PR": "wash_dry_60",
    "QUICK_WASH_DRY_PR_ONEGO_TWENTY_SIXTY_MIN": "quick_20_wash_dry_60",
    "QUICK_WASH_DRY_PR_WASHDRY60": "wash_dry_60",
    "QUICK_WASH_DRY_PR_QUICK20WASH_DRY60": "quick_20_wash_dry_60",
    "RAPID_PR_QUICK_15MIN": "quick_15",
    "RAPID_PR_RAPID_14MIN": "quick_14",
    "DRY_CLEANING_PR_REFRESH": "refresh",
    "RINSE": "prerinse",
    "RINSE_AND_SPIN": "rinse_spin",
    "SANITISE60_PR_ANTIALLERGY": "anti_allergy",
    "SANITISE60_PR_ANTIALLERGYVAPOUR": "anti_allergy_vapor",
    "SANITISE60_PR_HYGIENE": "hygiene",
    "SANITISE60_PR_SANITISE": "sanitize",
    "Shirts": "SHIRTS_PR_BUSINESSSHIRT",
    "SHOES_PR_RUNNINGSHOES": "running_shoes",
    "SILENT": "night",
    "SILK_DRY_PR_SILK": "silk",
    "SKIING_PR_SKIGEAR": "skiing_gear",
    "SKIING_PR_SKIINGGEAR": "skiing_gear",
    "SOCCER_RUGBY_PR_FOOTRUGBY": "soccer_rugby",
    "SOCCER_RUGBY_PR_SOCCER_RUGBY": "soccer_rugby",
    "SOCCER_RUGBY_SOCCER_RUGBY": "soccer_rugby",
    "SOFTENER_PR_RINSE": "rinse",
    "SPIN_PR_SPIN": "spin",
    "SPIN_PR_DRAIN_SPIN": "spin_drain",
    "SPORT_JACKETS_PR_OUTDOOR": "outdoor",
    "SPORT_JACKETS_PR_DOWN_JACKET": "down_jackets",
    "SPORT_JACKETS_PR_SKIING": "skiing_gear",
    "SPORTWEAR_PR_SPORTWEAR_WX": "sports",
    "SPORTS_PR_SPORT": "sports",
    "SPORTS_PR_MICROFIBRE": "microfiber",
    "SPORTWEAR_PR_SPORTWEAR": "sports",
    "SPORTWEAR_PR_SPORTWEARPLUS": "sports",
    "STEAM_DEWRINKLER_PR_VAPOURREFRESH": "vapor_refresh",
    "STEAM_DEWRINKLER_PR_STEAMCASHMERE": "steam_cashmere",
    "STEAM_REF_PR_STEAMREFRESH": "steam_refresh",
    "STEAM_REFRESH_PR_STEAM": "steam_refresh",
    "STEAM_REFRESH_PR_STEAMFRESHSCENT": "steam",
    "STEAM_REFRESH_PR_STEAMREFRESH": "steam_refresh",
    "SYNTHETIC_PR_SYNTHETICS": "synthetics",
    "SYNTHETIC_PR_BEDLINEN": "bed_linen",
    "SYNTHETIC_PR_BEDLINENXL": "bed_linen_xl",
    "SYNTHETIC_PR_EASYIRON": "easy_iron",
    "SYNTHETIC_PR_FLEECE": "fleece",
    "SYNTHETIC_PR_MICROFIBRE": "microfiber",
    "SYNTHETIC_PR_MIXED": "mixed",
    "SYNTHETIC_PR_SPORTWEAR": "sports",
    "SYNTHETIC_PR_SPORT": "sports",
    "TOWELS_PR_TOWELS": "towels",
    "TOWELS_PR_TOWELS_BASE": "towels",
    "TRAINING_GEAR_PR_DAILYTRAINING": "training_gear",
    "TRAINING_GEAR_PR_TRAININGGEAR": "training_gear",
    "UNIVERSAL_PR_MIXEDPLUSNOTXL": "mixed",
    "WASHERS_BASKET_CLEANING": "machine_clean",
    "WASHERS_COLORFUL": "colors",
    "WASHERS_DARK": "dark_clothes",
    "WASHERS_DUVET": "duvet",
    "WASHERS_HEAVY": "heavy_jeans",
    "WASHERS_NORMAL": "normal",
    "WASHERS_SOFT": "delicate_sport",
    "WASHERS_STAIN_REMOVAL": "stains_removal",
    "WASHERS_WHITE": "colors_light",
    "WHITES_LIGHT": "colors_light",
    "WOOL_GOLD_PR_WOOL": "wool",
    "WOOL_PR_WOOL": "wool_silk",
    "WOOL_PR_WOOL_HANDWASH": "wool_handwash",
    "WOOL_PR_WOOL_SILK": "wool_silk",
    "COTTON_PR_ECOWORKWEAR": "workwear",
    "WORKINGCLOTHES_PR_WORKINGCLOTHES": "workwear",
}


@dataclass(frozen=True, kw_only=True)
class ElectroluxSelectBaseDescription[T: ApplianceData, **P = []](
    SelectEntityDescription
):
    """Custom select description for Electrolux select."""

    command_mapper_fn: Callable[Concatenate[str, T, P], dict[str, Any]]
    exists_fn: Callable[Concatenate[T, P], bool]
    get_current_option: Callable[Concatenate[T, P], str]
    get_supported_options: Callable[Concatenate[T, P], list[str]]
    remote_control_check_fn: Callable[Concatenate[T, P], bool]
    available_fn: Callable[Concatenate[T, P], bool]
    electrolux_ha_map: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class ElectroluxSelectDescription[T: ApplianceData](
    ElectroluxSelectBaseDescription[T, []]
):
    """Custom select description for Electrolux select."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    available_fn: Callable[[T], bool] = lambda appliance: True


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleSelectDescription[T: ApplianceData](
    ElectroluxSelectBaseDescription[T, [str]]
):
    """Custom select description for Electrolux select for submodule appliances."""

    exists_fn: Callable[[T, str], bool] = lambda appliance, submodule: True
    available_fn: Callable[[T, str], bool] = lambda appliance, submodule: True


def set_temperature_option(
    option: str, appliance_data: WDAppliance | WMAppliance
) -> dict[str, Any]:
    """Send care temperature command."""

    current_program = appliance_data.get_current_program()
    return appliance_data.get_set_temperature_command(option, current_program)


def set_spin_speed_option(
    option: str, appliance_data: WDAppliance | WMAppliance
) -> dict[str, Any]:
    """Send spin speed command."""

    current_program = appliance_data.get_current_program()
    return appliance_data.get_set_spin_speed_command(option, current_program)


def set_care_program_option(
    option: str, appliance_data: DWAppliance | WDAppliance | WMAppliance | TDAppliance
) -> dict[str, Any]:
    """Send Care program command."""

    return appliance_data.get_set_program_command(option)


CARE_ELECTROLUX_SELECT: tuple[
    ElectroluxSelectDescription[DWAppliance | WDAppliance | WMAppliance | TDAppliance],
    ...,
] = (
    ElectroluxSelectDescription(
        key="program",
        translation_key="care_program",
        get_current_option=lambda appliance: appliance.get_current_program(),
        get_supported_options=lambda appliance: appliance.get_supported_programs(),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control() == RC_ENABLED
        ),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state()
            in (APPLIANCE_STATE_READY_TO_START, APPLIANCE_STATE_IDLE)
        ),
        command_mapper_fn=set_care_program_option,
        exists_fn=lambda appliance: appliance.is_feature_supported(PROGRAM_CAPABILITY),
        electrolux_ha_map=CARE_PROGRAM_TO_HA_OPTION,
    ),
)


WM_WD_ELECTROLUX_SELECT: tuple[
    ElectroluxSelectDescription[WDAppliance | WMAppliance], ...
] = (
    ElectroluxSelectDescription(
        key="temperature",
        translation_key="temperature",
        get_current_option=lambda appliance: appliance.get_current_temperature(),
        get_supported_options=lambda appliance: (
            appliance.get_feature_state_string_options(TEMPERATURE_CAPABILITY)
        ),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control() == RC_ENABLED
        ),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state() == APPLIANCE_STATE_READY_TO_START
        ),
        command_mapper_fn=set_temperature_option,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            TEMPERATURE_CAPABILITY
        ),
        electrolux_ha_map={
            "20_CELSIUS": "20_celsius",
            "30_CELSIUS": "30_celsius",
            "40_CELSIUS": "40_celsius",
            "50_CELSIUS": "50_celsius",
            "60_CELSIUS": "60_celsius",
            "95_CELSIUS": "95_celsius",
            "COLD": "cold",
        },
    ),
    ElectroluxSelectDescription(
        key="spin_speed",
        translation_key="spin_speed",
        get_current_option=lambda appliance: appliance.get_current_spin_speeds(),
        get_supported_options=lambda appliance: (
            appliance.get_feature_state_string_options(SPIN_SPEED_CAPABILITY)
        ),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control() == RC_ENABLED
        ),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state() == APPLIANCE_STATE_READY_TO_START
        ),
        command_mapper_fn=set_spin_speed_option,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            SPIN_SPEED_CAPABILITY
        ),
        electrolux_ha_map={
            "0_RPM": "0_rpm",
            "400_RPM": "400_rpm",
            "600_RPM": "600_rpm",
            "800_RPM": "800_rpm",
            "1000_RPM": "1000_rpm",
            "1200_RPM": "1200_rpm",
            "1400_RPM": "1400_rpm",
            "1600_RPM": "1600_rpm",
        },
    ),
)


def set_hb_fan_speed_option(option: str, appliance_data: HBAppliance) -> dict[str, Any]:
    """Send Hob hood fan speed command."""
    return appliance_data.get_hood_fan_speed_command(option)


def set_hb_state_option(option: str, appliance_data: HBAppliance) -> dict[str, Any]:
    """Send Hob hood state command."""
    return appliance_data.get_hood_state_command(option)


def set_hb_key_sound_tone(option: str, appliance_data: HBAppliance) -> dict[str, Any]:
    """Send sound tone command."""
    return appliance_data.get_key_sound_tone_command(option)


HB_ELECTROLUX_SELECT: tuple[ElectroluxSelectDescription[HBAppliance], ...] = (
    ElectroluxSelectDescription(
        key="hood_fan_speed",
        translation_key="hood_fan_speed",
        get_current_option=lambda appliance: appliance.get_current_hood_fan_speed(),
        get_supported_options=lambda appliance: (
            appliance.get_supported_hood_fan_speed()
        ),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control()
            in (RC_ENABLED, RC_NOT_SAFETY_RELEVANT_ENABLED)
        ),
        command_mapper_fn=set_hb_fan_speed_option,
        exists_fn=lambda appliance: appliance.is_hood_feature_supported(HOOD_FAN_SPEED),
        electrolux_ha_map=HOOD_FAN_SPEED_TO_HA_OPTION,
    ),
    ElectroluxSelectDescription(
        key="hood_state",
        translation_key="hood_state",
        get_current_option=lambda appliance: appliance.get_current_hood_state(),
        get_supported_options=lambda appliance: appliance.get_supported_hood_state(),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control()
            in (RC_ENABLED, RC_NOT_SAFETY_RELEVANT_ENABLED)
        ),
        command_mapper_fn=set_hb_state_option,
        exists_fn=lambda appliance: appliance.is_hood_feature_supported(HOOD_STATE),
        electrolux_ha_map={
            "AUTOMATIC": "auto",
            "MANUAL": "manual",
        },
    ),
    ElectroluxSelectDescription(
        key="sound_tone",
        translation_key="sound_tone",
        get_current_option=lambda appliance: appliance.get_current_key_sound_tone(),
        get_supported_options=lambda appliance: (
            appliance.get_supported_key_sound_tone()
        ),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control()
            in (RC_ENABLED, RC_NOT_SAFETY_RELEVANT_ENABLED)
        ),
        command_mapper_fn=set_hb_key_sound_tone,
        exists_fn=lambda appliance: appliance.is_feature_supported(KEY_SOUND_TONE),
        electrolux_ha_map={"CLICK": "click", "NONE": "none"},
    ),
)


def set_hd_fan_level_option(option: str, appliance_data: HDAppliance) -> dict[str, Any]:
    """Send hood fan level command."""
    return appliance_data.get_set_hood_fan_level_command(option)


HD_ELECTROLUX_SELECT: tuple[ElectroluxSelectDescription[HDAppliance], ...] = (
    ElectroluxSelectDescription(
        key="hood_fan_speed",
        translation_key="hood_fan_speed",
        get_current_option=lambda appliance: appliance.get_current_hood_fan_level(),
        get_supported_options=lambda appliance: (
            appliance.get_supported_hood_fan_level()
        ),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control()
            in (RC_ENABLED, RC_NOT_SAFETY_RELEVANT_ENABLED)
        ),
        command_mapper_fn=set_hd_fan_level_option,
        exists_fn=lambda appliance: appliance.is_feature_supported(HOOD_FAN_LEVEL),
        electrolux_ha_map=HOOD_FAN_SPEED_TO_HA_OPTION,
    ),
)


def set_ov_program_option(option: str, appliance_data: OVAppliance) -> dict[str, Any]:
    """Send OV program command."""
    return appliance_data.get_program_command(option)


OV_ELECTROLUX_SELECT: tuple[ElectroluxSelectDescription[OVAppliance], ...] = (
    ElectroluxSelectDescription(
        key="program",
        translation_key="oven_program",
        get_current_option=lambda appliance: appliance.get_current_program(),
        get_supported_options=lambda appliance: appliance.get_supported_programs(),
        remote_control_check_fn=lambda appliance: (
            appliance.get_current_remote_control() == RC_ENABLED
        ),
        available_fn=lambda appliance: (
            appliance.get_current_appliance_state() != APPLIANCE_STATE_RUNNING
        ),
        command_mapper_fn=set_ov_program_option,
        exists_fn=lambda appliance: appliance.is_feature_supported(PROGRAM),
        electrolux_ha_map=OVEN_PROGRAM_TO_HA_OPTION,
    ),
)


def set_so_program_option(
    option: str, appliance_data: SOAppliance, cavity: str
) -> dict[str, Any]:
    """Send SO program command."""
    return appliance_data.get_program_command(cavity, option)


SO_ELECTROLUX_SELECT: tuple[ElectroluxSubmoduleSelectDescription[SOAppliance], ...] = (
    ElectroluxSubmoduleSelectDescription[SOAppliance](
        key="program",
        translation_key="oven_program",
        get_current_option=lambda appliance, submodule: (
            appliance.get_current_cavity_program(submodule)
        ),
        get_supported_options=lambda appliance, submodule: (
            appliance.get_cavity_supported_programs(submodule)
        ),
        remote_control_check_fn=lambda appliance, submodule: (
            appliance.get_current_remote_control() == RC_ENABLED
        ),
        available_fn=lambda appliance, submodule: (
            appliance.get_current_cavity_appliance_state(submodule)
            != APPLIANCE_STATE_RUNNING
        ),
        command_mapper_fn=set_so_program_option,
        exists_fn=lambda appliance, submodule: appliance.is_cavity_feature_supported(
            submodule, PROGRAM
        ),
        electrolux_ha_map=OVEN_PROGRAM_TO_HA_OPTION,
    ),
)


def set_dh_fan_speed_option(option: str, appliance_data: DHAppliance) -> dict[str, Any]:
    """Send dehumidifier fan speed command."""
    return appliance_data.get_fan_speed_command(option)


DH_ELECTROLUX_SELECT: tuple[ElectroluxSelectDescription[DHAppliance], ...] = (
    ElectroluxSelectDescription(
        key="dehumidifier_fan_speed",
        translation_key="dehumidifier_fan_speed",
        get_current_option=lambda appliance: appliance.get_current_fan_speed(),
        get_supported_options=lambda appliance: appliance.get_supported_fan_speeds(),
        remote_control_check_fn=lambda appliance: True,
        command_mapper_fn=set_dh_fan_speed_option,
        exists_fn=lambda appliance: appliance.is_feature_supported(FAN_SPEED),
        electrolux_ha_map=DEHUMIDIFIER_FAN_SPEED_TO_HA_OPTION,
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, (DWAppliance, TDAppliance, WMAppliance, WDAppliance)):
        entities.extend(
            ElectroluxSelectEntity(appliance_data, coordinator, description)
            for description in CARE_ELECTROLUX_SELECT
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, (WDAppliance, WMAppliance)):
        entities.extend(
            ElectroluxSelectEntity(appliance_data, coordinator, description)
            for description in WM_WD_ELECTROLUX_SELECT
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, HBAppliance):
        entities.extend(
            ElectroluxSelectEntity(appliance_data, coordinator, description)
            for description in HB_ELECTROLUX_SELECT
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, HDAppliance):
        entities.extend(
            ElectroluxSelectEntity(appliance_data, coordinator, description)
            for description in HD_ELECTROLUX_SELECT
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxSelectEntity(appliance_data, coordinator, description)
            for description in OV_ELECTROLUX_SELECT
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, SOAppliance):
        entities.extend(
            ElectroluxSubmoduleSelectEntity(
                appliance_data, coordinator, description, cavity
            )
            for cavity in appliance_data.get_supported_cavities()
            for description in SO_ELECTROLUX_SELECT
            if appliance_data.is_cavity_feature_supported(cavity, PROGRAM)
        )

    if isinstance(appliance_data, DHAppliance):
        entities.extend(
            ElectroluxSelectEntity(appliance_data, coordinator, description)
            for description in DH_ELECTROLUX_SELECT
            if description.exists_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set Select entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBaseSelect[T: ApplianceData, **P](
    ElectroluxBaseEntity[T], SelectEntity
):
    """Base class for Electrolux select entities."""

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        key: str,
        description: ElectroluxSelectBaseDescription[T, P],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(appliance_data, coordinator, key)

        supported_electrolux_options = self._get_supported_electrolux_options()
        electrolux_to_ha_map: dict[str, str] = {}

        already_seen_options = set()
        read_only_options = set()

        for electrolux_option in supported_electrolux_options:
            ha_option = description.electrolux_ha_map.get(electrolux_option)
            if ha_option is not None:
                if ha_option in already_seen_options:
                    read_only_options.add(ha_option)
                already_seen_options.add(ha_option)
                electrolux_to_ha_map[electrolux_option] = ha_option
            else:
                _LOGGER.warning(
                    "Unmapped Electrolux option found for %s: %s",
                    self.entity_description.key,
                    electrolux_option,
                )

        self._electrolux_to_ha_map = electrolux_to_ha_map
        self._ha_to_electrolux_map = {
            ha_option: electrolux_option
            for electrolux_option, ha_option in self._electrolux_to_ha_map.items()
            if ha_option not in read_only_options
        }

        options_list = list(already_seen_options)
        options_list.sort()

        self._attr_options = options_list

    @override
    def _update_attr_state(self) -> bool:
        state_changed = False

        new_option = self._get_current_option()
        if self._attr_current_option != new_option:
            self._attr_current_option = new_option
            state_changed = True

        return state_changed

    def _get_current_option(self) -> str | None:
        """Return the current Home Assistant option for the select entity."""
        electrolux_option = self._get_current_electrolux_option()
        if electrolux_option is None:
            return None
        ha_option = self._electrolux_to_ha_map.get(electrolux_option)
        if ha_option is None:
            _LOGGER.warning(
                "Unmapped Electrolux option found for %s: %s",
                self.entity_description.key,
                electrolux_option,
            )
        return ha_option

    @abstractmethod
    def _get_supported_electrolux_options(self) -> list[str]:
        """Return the supported Electrolux options for the select entity."""

    @abstractmethod
    def _get_current_electrolux_option(self) -> str | None:
        """Return the current Electrolux option for the select entity."""

    @abstractmethod
    def _is_remote_control_enabled(self) -> bool:
        """Return True if remote control is enabled for the appliance."""

    @abstractmethod
    def _is_available_state(self) -> bool:
        """Return True if the appliance is in a state where changing the selected option is available."""

    @abstractmethod
    def _get_command(self, option: str) -> dict[str, Any]:
        """Return the command to send to the appliance for the given option."""

    @override
    async def async_select_option(self, option: str) -> None:
        """Send command to the appliance."""
        if not self._is_remote_control_enabled():
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="remote_control_disabled"
            )
        if not self._is_available_state():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_state_for_command",
            )

        electrolux_option = self._ha_to_electrolux_map.get(option)
        if electrolux_option is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="read_only_option",
            )

        command = self._get_command(electrolux_option)
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()


class ElectroluxSelectEntity[T: ApplianceData](ElectroluxBaseSelect[T, []]):
    """Generic Electrolux select entity."""

    entity_description: ElectroluxSelectDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSelectDescription[T],
    ) -> None:
        """Initialize the select entity."""
        self.entity_description = description
        super().__init__(appliance_data, coordinator, description.key, description)

    @override
    def _get_supported_electrolux_options(self) -> list[str]:
        return self.entity_description.get_supported_options(self._appliance_data)

    @override
    def _get_current_electrolux_option(self) -> str | None:
        return self.entity_description.get_current_option(self._appliance_data)

    @override
    def _is_remote_control_enabled(self) -> bool:
        return self.entity_description.remote_control_check_fn(self._appliance_data)

    @override
    def _is_available_state(self) -> bool:
        return self.entity_description.available_fn(self._appliance_data)

    @override
    def _get_command(self, option: str) -> dict[str, Any]:
        return self.entity_description.command_mapper_fn(option, self._appliance_data)


class ElectroluxSubmoduleSelectEntity[T: ApplianceData](ElectroluxBaseSelect[T, [str]]):
    """Generic Electrolux submodule select entity."""

    entity_description: ElectroluxSubmoduleSelectDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSubmoduleSelectDescription[T],
        cavity: str,
    ) -> None:
        """Init select cavity program entity."""
        self.entity_description = description
        self._cavity = cavity
        entity_key = f"{convert_to_snake_case(cavity)}_{description.key}"
        translation_key = (
            f"{convert_to_snake_case(cavity)}_{description.translation_key}"
        )
        super().__init__(appliance_data, coordinator, entity_key, description)
        self._attr_translation_key = translation_key

    @override
    def _get_supported_electrolux_options(self) -> list[str]:
        return self.entity_description.get_supported_options(
            self._appliance_data, self._cavity
        )

    @override
    def _get_current_electrolux_option(self) -> str | None:
        return self.entity_description.get_current_option(
            self._appliance_data, self._cavity
        )

    @override
    def _is_remote_control_enabled(self) -> bool:
        return self.entity_description.remote_control_check_fn(
            self._appliance_data, self._cavity
        )

    @override
    def _is_available_state(self) -> bool:
        return self.entity_description.available_fn(self._appliance_data, self._cavity)

    @override
    def _get_command(self, option: str) -> dict[str, Any]:
        return self.entity_description.command_mapper_fn(
            option, self._appliance_data, self._cavity
        )
