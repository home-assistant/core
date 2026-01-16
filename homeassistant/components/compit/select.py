"""Select platform for Compit integration."""

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator
from .entity import CompitEntityDescription

SELECT_PARAM_TYPE = "Select"
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CompitSelectDescription(CompitEntityDescription, SelectEntityDescription):
    """Class to describe a Compit select entity."""

    has_entity_name: bool = True
    """Whether to include the entity name in the select entity name."""

    options_dict: dict[int, str]
    """The available options for the select entity."""


@dataclass(frozen=True, kw_only=True)
class CompitDeviceDescription:
    """Class to describe a Compit device."""

    name: str
    """Name of the device."""

    parameters: dict[str, CompitSelectDescription]
    """Parameters of the device."""

    _class: int
    """Class of the device."""


DEVICE_DEFINITIONS: dict[int, CompitDeviceDescription] = {
    223: CompitDeviceDescription(
        name="Nano Color 2",
        parameters={
            "__trybpracyinstalacji": CompitSelectDescription(
                key="__trybpracyinstalacji",
                translation_key="nano_color_2_installation_season",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                    2: "cooling",
                },
            ),
            "__język": CompitSelectDescription(
                key="__język",
                translation_key="nano_color_2_language",
                icon="mdi:translate",
                options_dict={
                    0: "polish",
                    1: "english",
                },
            ),
            "__aerokonfbypass": CompitSelectDescription(
                key="__aerokonfbypass",
                translation_key="nano_color_2_by_pass",
                icon="mdi:valve",
                options_dict={
                    0: "off",
                    1: "car",
                    2: "on",
                },
            ),
            "__trybaero": CompitSelectDescription(
                key="__trybaero",
                translation_key="nano_color_2_ventilation_operating_mode",
                icon="mdi:fan",
                options_dict={
                    5: "work_by_clock_zones_work_by_zones",
                    4: "christmas_work",
                    3: "gear_3",
                    2: "heat_2",
                    1: "gear_1",
                    0: "gear_0",
                },
            ),
            "__trybaero2": CompitSelectDescription(
                key="__trybaero2",
                translation_key="nano_color_2_ventilation_flight",
                icon="mdi:fan",
                options_dict={
                    1: "gear_1",
                    2: "heat_2",
                    3: "gear_3",
                    4: "gear_4_airing",
                    0: "gear_0",
                },
            ),
            "__trybpracytermostatu": CompitSelectDescription(
                key="__trybpracytermostatu",
                translation_key="nano_color_2_thermostat_operating_mode",
                icon="mdi:thermostat",
                options_dict={
                    0: "work_according_to_clock_zones",
                    1: "christmas_work",
                    2: "manual_work",
                    3: "away_from_home",
                },
            ),
            "__a5prpozadomem": CompitSelectDescription(
                key="__a5prpozadomem",
                translation_key="nano_color_2_out_of_home_program",
                icon="mdi:calendar-clock",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work30m_stop",
                    2: "20m_work40m_stop",
                    3: "20m_work100m_stop",
                },
            ),
            "__a5nagrzwtorna": CompitSelectDescription(
                key="__a5nagrzwtorna",
                translation_key="nano_color_2_secondary_heater",
                icon="mdi:radiator",
                options_dict={
                    0: "disabled",
                    1: "pwm",
                },
            ),
            "__a4prpozadomem": CompitSelectDescription(
                key="__a4prpozadomem",
                translation_key="nano_color_2_out_of_home_program",
                icon="mdi:calendar-clock",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work_30m_stop",
                    2: "20m_work_40m_stop",
                    3: "20m_work_100m_stop",
                },
            ),
        },
        _class=10,
    ),
    12: CompitDeviceDescription(
        name="Nano Color",
        parameters={
            "__trybpracyinstalacji": CompitSelectDescription(
                key="__trybpracyinstalacji",
                translation_key="nano_color_installation_season",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                    2: "cooling",
                },
            ),
            "__język": CompitSelectDescription(
                key="__język",
                translation_key="nano_color_language",
                icon="mdi:translate",
                options_dict={
                    0: "polish",
                    1: "english",
                },
            ),
            "__aerokonfbypass": CompitSelectDescription(
                key="__aerokonfbypass",
                translation_key="nano_color_by_pass",
                icon="mdi:valve",
                options_dict={
                    0: "off",
                    1: "car",
                    2: "on",
                },
            ),
            "__trybaero": CompitSelectDescription(
                key="__trybaero",
                translation_key="nano_color_ventilation_operating_mode",
                icon="mdi:fan",
                options_dict={
                    5: "work_by_clock_zones_work_by_zones",
                    4: "christmas_work",
                    3: "gear_3",
                    2: "heat_2",
                    1: "gear_1",
                    0: "gear_0",
                },
            ),
            "__trybaero2": CompitSelectDescription(
                key="__trybaero2",
                translation_key="nano_color_ventilation_flight",
                icon="mdi:fan",
                options_dict={
                    1: "gear_1",
                    2: "heat_2",
                    3: "gear_3",
                    4: "gear_4_airing",
                    0: "gear_0",
                },
            ),
            "__trybpracytermostatu": CompitSelectDescription(
                key="__trybpracytermostatu",
                translation_key="nano_color_thermostat_operating_mode",
                icon="mdi:thermostat",
                options_dict={
                    0: "work_according_to_clock_zones",
                    1: "christmas_work",
                    2: "manual_work",
                    3: "away_from_home",
                },
            ),
            "__a5prpozadomem": CompitSelectDescription(
                key="__a5prpozadomem",
                translation_key="nano_color_out_of_home_program",
                icon="mdi:calendar-clock",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work30m_stop",
                    2: "20m_work40m_stop",
                    3: "20m_work100m_stop",
                },
            ),
            "__a5nagrzwtorna": CompitSelectDescription(
                key="__a5nagrzwtorna",
                translation_key="nano_color_secondary_heater",
                icon="mdi:radiator",
                options_dict={
                    0: "disabled",
                    1: "pwm",
                },
            ),
            "__a4prpozadomem": CompitSelectDescription(
                key="__a4prpozadomem",
                translation_key="nano_color_out_of_home_program",
                icon="mdi:calendar-clock",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work_30m_stop",
                    2: "20m_work_40m_stop",
                    3: "20m_work_100m_stop",
                },
            ),
        },
        _class=10,
    ),
    7: CompitDeviceDescription(
        name="Nano One",
        parameters={
            "_jezyk": CompitSelectDescription(
                key="_jezyk",
                translation_key="nano_one_language",
                icon="mdi:translate",
                options_dict={
                    0: "polish",
                    1: "english",
                },
            ),
            "__visibledevices": CompitSelectDescription(
                key="__visibledevices",
                translation_key="nano_one_visible_devices",
                icon="mdi:eye-outline",
                options_dict={
                    0: "lack",
                    1: "all",
                    2: "boilerheat_pump_1",
                    3: "boiler_2",
                    4: "r450",
                    5: "r430",
                    6: "mixer_1",
                    7: "mixer_2",
                    8: "mixer_3",
                    9: "mixer_4",
                    10: "solar_nr_1",
                },
            ),
            "__info1screen": CompitSelectDescription(
                key="__info1screen",
                translation_key="nano_one_info_first_screen",
                icon="mdi:monitor-dashboard",
                options_dict={
                    0: "lack",
                    1: "outer_t",
                    2: "t_co_1",
                    3: "t_mixer_1",
                },
            ),
            "__mode_intal": CompitSelectDescription(
                key="__mode_intal",
                translation_key="nano_one_installation_mode",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                    2: "cooling",
                },
            ),
            "__nano_mode": CompitSelectDescription(
                key="__nano_mode",
                translation_key="nano_one_nano_work",
                icon="mdi:cog-outline",
                options_dict={
                    0: "manual_run_3",
                    1: "manual_run_2_reczny",
                    2: "manual_run_1",
                    3: "manual_run_0",
                    4: "wg_zegara_program",
                    5: "christmas_program",
                    6: "out_of_home_program",
                },
            ),
            "__wentkomfort": CompitSelectDescription(
                key="__wentkomfort",
                translation_key="nano_one_ventilation_in_the_comfort_zone",
                icon="mdi:fan",
                options_dict={
                    0: "stop",
                    1: "gear_1",
                    2: "heat_2",
                    3: "gear_3",
                },
            ),
            "__wenteko": CompitSelectDescription(
                key="__wenteko",
                translation_key="nano_one_ventilation_in_the_eco_zone",
                icon="mdi:fan",
                options_dict={
                    0: "stop",
                    1: "gear_1",
                    2: "heat_2",
                    3: "gear_3",
                },
            ),
            "__wenturlop": CompitSelectDescription(
                key="__wenturlop",
                translation_key="nano_one_ventilation_in_the_away_mode",
                icon="mdi:fan",
                options_dict={
                    0: "stop",
                    1: "gear_1",
                    2: "heat_2",
                    3: "gear_3",
                },
            ),
            "__a3programwietrzenia": CompitSelectDescription(
                key="__a3programwietrzenia",
                translation_key="nano_one_aero_3_airing_program",
                icon="mdi:calendar-clock",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work30m_stop",
                    2: "20m_work40m_stop",
                    3: "20m_work100m_stop",
                },
            ),
            "__a3konfignagwst": CompitSelectDescription(
                key="__a3konfignagwst",
                translation_key="nano_one_aero_3_pre_heater_setup",
                icon="mdi:radiator",
                options_dict={
                    0: "disabled",
                    1: "onoff",
                    2: "attached_pwm",
                },
            ),
            "__a3konfignagwt": CompitSelectDescription(
                key="__a3konfignagwt",
                translation_key="nano_one_aero_3_secondary_heater_configuration",
                icon="mdi:radiator",
                options_dict={
                    0: "disabled",
                    1: "onoff_tpom_function",
                    2: "onoff_tnaw_function",
                    3: "onoff_function",
                    4: "pwm_tpom_function",
                    5: "pwm_tnaw_function",
                },
            ),
            "__a3fwepress": CompitSelectDescription(
                key="__a3fwepress",
                translation_key="nano_one_aero_3_function_in_a_pressure_switch",
                icon="mdi:gauge",
                options_dict={
                    0: "exchanger_freezing",
                    1: "dirty_air_filter",
                    2: "weathering",
                    3: "extract",
                },
            ),
            "__a3konfigpk3": CompitSelectDescription(
                key="__a3konfigpk3",
                translation_key="nano_one_aero_3_pk3_configuration",
                icon="mdi:cog-outline",
                options_dict={
                    0: "central_square",
                    1: "what_heating",
                },
            ),
            "__a3konfigrozmr": CompitSelectDescription(
                key="__a3konfigrozmr",
                translation_key="nano_one_aero_3_defrost_configuration",
                icon="mdi:snowflake-melt",
                options_dict={
                    0: "off_fan",
                    1: "incl_nag_initial",
                    2: "incl_nag_wst_50_aisle",
                    3: "opening_a_by_pass",
                },
            ),
            "__a5prwietrz": CompitSelectDescription(
                key="__a5prwietrz",
                translation_key="nano_one_aero_5_ventilation_program",
                icon="mdi:fan",
                options_dict={
                    0: "continuous_operation",
                    1: "praca_30min_co_30min",
                    2: "praca_20min_co_40min",
                    3: "praca_20min_co_100min",
                },
            ),
            "__a5trybnagrzwst": CompitSelectDescription(
                key="__a5trybnagrzwst",
                translation_key="nano_one_aero_5_heat_mode_initial",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "onoff",
                    2: "attached_pwm",
                },
            ),
            "__a5trnagrzgl": CompitSelectDescription(
                key="__a5trnagrzgl",
                translation_key="nano_one_aero_5_heat_mode_main",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "attached_pwm",
                },
            ),
            "__a5metrozmr": CompitSelectDescription(
                key="__a5metrozmr",
                translation_key="nano_one_aero_5_defrosting_method",
                icon="mdi:snowflake-melt",
                options_dict={
                    0: "off_fan",
                    1: "incl_pre_heater",
                    2: "opening_a_by_pass",
                },
            ),
            "__a5funkcpresost": CompitSelectDescription(
                key="__a5funkcpresost",
                translation_key="nano_one_aero_5_pressure_switch_function",
                icon="mdi:gauge",
                options_dict={
                    0: "exchanger_freezing",
                    1: "dirty_air_filter",
                    2: "weathering",
                    3: "extract",
                },
            ),
            "__a4programwietrzenia": CompitSelectDescription(
                key="__a4programwietrzenia",
                translation_key="nano_one_aero_4_airing_program",
                icon="mdi:fan",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work30m_stop",
                    2: "20m_work40m_stop",
                    3: "20m_work100m_stop",
                },
            ),
            "__a4konfigbypass": CompitSelectDescription(
                key="__a4konfigbypass",
                translation_key="nano_one_aero_4_by_pass_configuration",
                icon="mdi:valve",
                options_dict={
                    0: "lack",
                    1: "simplified",
                    2: "fun_rooms",
                    3: "fun_exhaust_air",
                },
            ),
            "__a4trregnaw": CompitSelectDescription(
                key="__a4trregnaw",
                translation_key="nano_one_aero_4_air_temperature_control_mode",
                icon="mdi:thermometer",
                options_dict={
                    0: "indoor_function",
                    1: "cutting_function",
                    2: "exhaust_function",
                },
            ),
            "__a4konfpk3": CompitSelectDescription(
                key="__a4konfpk3",
                translation_key="nano_one_aero_4_r3_function",
                icon="mdi:cog-outline",
                options_dict={
                    0: "what_heating",
                    1: "throttle",
                    2: "no_brak_features",
                },
            ),
            "__a4konfrozmr": CompitSelectDescription(
                key="__a4konfrozmr",
                translation_key="nano_one_aero_4_defrosting_method",
                icon="mdi:snowflake-melt",
                options_dict={
                    0: "turning_off_the_fan",
                    1: "switching_on_the_heater_initial",
                    2: "switching_on_the_heater_wst_50_aisle",
                    3: "opening_a_by_pass",
                },
            ),
            "__a4_konfig_we_di2": CompitSelectDescription(
                key="__a4_konfig_we_di2",
                translation_key="nano_one_aero_4_di2_input_configuration",
                icon="mdi:cog-outline",
                options_dict={
                    0: "weathering",
                    1: "extract",
                },
            ),
        },
        _class=10,
    ),
    224: CompitDeviceDescription(
        name="R 900",
        parameters={
            "__typ_obwo_co1": CompitSelectDescription(
                key="__typ_obwo_co1",
                translation_key="r_900_circuit_type_co1",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
            ),
            "__zrod_kore_co1": CompitSelectDescription(
                key="__zrod_kore_co1",
                translation_key="r_900_source_of_the_co1_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "thermostat",
                    3: "nano_nr1",
                    4: "nano_nr2",
                    5: "nano_nr3",
                    6: "nano_nr4",
                    7: "nano_nr5",
                },
            ),
            "__typ_obwo_co2": CompitSelectDescription(
                key="__typ_obwo_co2",
                translation_key="r_900_co2_circuit_type",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
            ),
            "__zrod_kore_co2": CompitSelectDescription(
                key="__zrod_kore_co2",
                translation_key="r_900_source_of_co2_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "thermostat",
                    3: "nano_nr1",
                    4: "nano_nr2",
                    5: "nano_nr3",
                    6: "nano_nr4",
                    7: "nano_nr5",
                },
            ),
            "__typ_obwo_co3": CompitSelectDescription(
                key="__typ_obwo_co3",
                translation_key="r_900_circuit_type_co3",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
            ),
            "__zrod_kore_co3": CompitSelectDescription(
                key="__zrod_kore_co3",
                translation_key="r_900_source_of_co3_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "thermostat",
                    3: "nano_nr1",
                    4: "nano_nr2",
                    5: "nano_nr3",
                    6: "nano_nr4",
                    7: "nano_nr5",
                },
            ),
            "__typ_obwo_co4": CompitSelectDescription(
                key="__typ_obwo_co4",
                translation_key="r_900_circuit_type_co4",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
            ),
            "__zrod_kore_co4": CompitSelectDescription(
                key="__zrod_kore_co4",
                translation_key="r_900_source_of_co4_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "thermostat",
                    3: "nano_nr1",
                    4: "nano_nr2",
                    5: "nano_nr3",
                    6: "nano_nr4",
                    7: "nano_nr5",
                },
            ),
            "__cyrk_cwu": CompitSelectDescription(
                key="__cyrk_cwu",
                translation_key="r_900_hot_water_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "in_clock_zones",
                    2: "constant",
                },
            ),
            "__tr_pracy_pc": CompitSelectDescription(
                key="__tr_pracy_pc",
                translation_key="r_900_pump_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "off",
                    1: "eco",
                    2: "hybrid",
                },
            ),
            "__tr_pr_co1": CompitSelectDescription(
                key="__tr_pr_co1",
                translation_key="r_900_operating_mode_co1_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "program",
                    2: "manual",
                },
            ),
            "__tr_pr_co2": CompitSelectDescription(
                key="__tr_pr_co2",
                translation_key="r_900_operating_mode_co2_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "program",
                    2: "manual",
                },
            ),
            "__tr_pr_co3": CompitSelectDescription(
                key="__tr_pr_co3",
                translation_key="r_900_operating_mode_co3_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "program",
                    2: "manual",
                },
            ),
            "__tr_pr_co4": CompitSelectDescription(
                key="__tr_pr_co4",
                translation_key="r_900_operating_mode_co4_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "program",
                    2: "manual",
                },
            ),
        },
        _class=47,
    ),
    3: CompitDeviceDescription(
        name="R810",
        parameters={
            "__pracamieszacza": CompitSelectDescription(
                key="__pracamieszacza",
                translation_key="r810_mixer_operation",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "nano_1",
                    5: "nano_2",
                    6: "nano_3",
                    7: "nano_4",
                    8: "nano_5",
                },
            ),
            "__trybwc14": CompitSelectDescription(
                key="__trybwc14",
                translation_key="r810_network_operation_mode_c14",
                icon="mdi:lan",
                options_dict={
                    0: "subordinate",
                    1: "master",
                },
            ),
        },
        _class=14,
    ),
    45: CompitDeviceDescription(
        name="SolarComp971",
        parameters={
            "__trybpracy": CompitSelectDescription(
                key="__trybpracy",
                translation_key="solarcomp971_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    1: "car",
                    2: "de_icing",
                    3: "holiday",
                    4: "disable",
                },
            ),
        },
        _class=18,
    ),
    44: CompitDeviceDescription(
        name="SolarComp 951",
        parameters={
            "__typcieplomierza": CompitSelectDescription(
                key="__typcieplomierza",
                translation_key="solarcomp_951_heat_meter_type",
                icon="mdi:solar-power",
                options_dict={
                    1: "1",
                    2: "2",
                    3: "3",
                    4: "4",
                },
            ),
            "__typplynusolar": CompitSelectDescription(
                key="__typplynusolar",
                translation_key="solarcomp_951_solar_fluid_type",
                icon="mdi:solar-power",
                options_dict={
                    0: "water",
                    1: "ergolid_eko_15c",
                    2: "ergolid_eko_20c",
                    3: "ergolid_eko_25c",
                    4: "ergolid_eko_35c",
                    5: "transtherm_n_15c",
                    6: "transtherm_n_20c",
                    7: "transtherm_n_25c",
                    8: "transtherm_n_35c",
                    9: "transtherm_eko_15c",
                    10: "transtherm_eko_20c",
                    11: "transtherm_eko_25c",
                    12: "transtherm_eko_35c",
                    13: "terms_eco_concentrate",
                    14: "termsol_eco_15c",
                    15: "termsol_eco_20c",
                    16: "termsol_eco_25c",
                    17: "termsol_eco_35c",
                    18: "termsol_eco_pro_35c",
                    19: "immericol_borighicol_pg_35c",
                    20: "immericol_alu_borighicol_pg_30c_alu",
                    21: "esol_29c",
                    22: "lajt_sol_29c",
                },
            ),
            "__trybpracy": CompitSelectDescription(
                key="__trybpracy",
                translation_key="solarcomp_951_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    1: "automatic_operation",
                    2: "de_icing",
                    3: "holiday",
                    4: "disable",
                },
            ),
        },
        _class=18,
    ),
    92: CompitDeviceDescription(
        name="r490",
        parameters={
            "__typprzycisku": CompitSelectDescription(
                key="__typprzycisku",
                translation_key="r490_graphics_model",
                icon="mdi:image-outline",
                options_dict={
                    0: "3d",
                    1: "2d",
                },
            ),
            "__co1zrodlokorekty": CompitSelectDescription(
                key="__co1zrodlokorekty",
                translation_key="r490_co1_source_of_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "termosta",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr6",
                },
            ),
            "_co2zrodlokorekty": CompitSelectDescription(
                key="_co2zrodlokorekty",
                translation_key="r490_co2_the_source_of_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "termosta",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            ),
            "__co3zrodlokorekty": CompitSelectDescription(
                key="__co3zrodlokorekty",
                translation_key="r490_co3_the_source_of_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            ),
            "__co4zrkorekty": CompitSelectDescription(
                key="__co4zrkorekty",
                translation_key="r490_co4_the_source_of_correction",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "clock",
                    2: "termosta",
                    3: "nano_nr_1",
                    4: "nano",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            ),
            "__sezprinst": CompitSelectDescription(
                key="__sezprinst",
                translation_key="r490_installation_working_season",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "stop",
                    1: "echo",
                    2: "hybrid",
                },
            ),
            "__trybprcwu": CompitSelectDescription(
                key="__trybprcwu",
                translation_key="r490_dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    1: "work_according_to_clock_zones",
                    2: "manual_work",
                },
            ),
            "__trprco1": CompitSelectDescription(
                key="__trprco1",
                translation_key="r490_co1_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "stop",
                    1: "program",
                    2: "manual_work",
                },
            ),
            "__trprco2": CompitSelectDescription(
                key="__trprco2",
                translation_key="r490_co2_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "stop",
                    1: "program",
                    2: "manual_work",
                },
            ),
            "__trprco3": CompitSelectDescription(
                key="__trprco3",
                translation_key="r490_co3_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "stop",
                    1: "program",
                    2: "manual_work",
                },
            ),
            "__trprco4": CompitSelectDescription(
                key="__trprco4",
                translation_key="r490_co4_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "stop",
                    1: "program",
                    2: "manual_work",
                },
            ),
            "__trprbufora": CompitSelectDescription(
                key="__trprbufora",
                translation_key="r490_buffer_mode",
                icon="mdi:database",
                options_dict={
                    0: "stop",
                    1: "program",
                    2: "manual_work",
                },
            ),
        },
        _class=33,
    ),
    34: CompitDeviceDescription(
        name="r470",
        parameters={
            "__instmode": CompitSelectDescription(
                key="__instmode",
                translation_key="r470_installation_mode",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                    2: "summer_cooling",
                },
            ),
            "__mode": CompitSelectDescription(
                key="__mode",
                translation_key="r470_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    1: "disable",
                    2: "car",
                    3: "echo",
                },
            ),
            "__comode": CompitSelectDescription(
                key="__comode",
                translation_key="r470_work_every",
                icon="mdi:cog-outline",
                options_dict={
                    1: "no_corrections",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "z_nano_1",
                    5: "z_nano_2",
                    6: "with_nano_3",
                    7: "z_nano_4",
                    8: "z_nano_5",
                },
            ),
            "__mixer1mode": CompitSelectDescription(
                key="__mixer1mode",
                translation_key="r470_mixer_operation_1",
                icon="mdi:mixer",
                options_dict={
                    1: "no_corrections",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "z_nano_1",
                    5: "z_nano_2",
                    6: "with_nano_3",
                    7: "z_nano_4",
                    8: "z_nano_5",
                },
            ),
            "__dhwmode": CompitSelectDescription(
                key="__dhwmode",
                translation_key="r470_dhw_mode_of_operation",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "works_constantly",
                    2: "by_the_clock",
                },
            ),
            "__dhwcircmode": CompitSelectDescription(
                key="__dhwcircmode",
                translation_key="r470_dhw_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "works_constantly",
                    2: "by_the_clock",
                },
            ),
            "__fazapracy": CompitSelectDescription(
                key="__fazapracy",
                translation_key="r470_work_phase",
                icon="mdi:sine-wave",
                options_dict={
                    0: "initialization",
                    1: "stop",
                    2: "stop",
                    3: "work",
                    4: "block_tdz",
                    5: "press_h",
                    6: "press_l",
                    7: "thawing",
                    8: "uszk_tgz_sensor",
                    9: "uszk_tdz_sensor",
                    10: "uszk_freon_sensor",
                    11: "no_communication_with_e8",
                    12: "awaria_mod_h5",
                    13: "blockade",
                },
            ),
            "__pdz": CompitSelectDescription(
                key="__pdz",
                translation_key="r470_pump_dz",
                icon="mdi:water-pump",
                options_dict={
                    0: "off",
                    1: "on",
                    2: "valve",
                    3: "pump_dz_valve",
                },
            ),
        },
        _class=16,
    ),
    91: CompitDeviceDescription(
        name="R770RS / R771RS",
        parameters={
            "__trybpompymiesz1": CompitSelectDescription(
                key="__trybpompymiesz1",
                translation_key="r770rs_r771rs_disable_thermostatic_co1_pump",
                icon="mdi:thermostat",
                options_dict={
                    0: "continuous_operation",
                    1: "switched_off_by_thermostat",
                },
            ),
            "__trybmieszacza": CompitSelectDescription(
                key="__trybmieszacza",
                translation_key="r770rs_r771rs_lowering_source_mixer1",
                icon="mdi:mixer",
                options_dict={
                    0: "lack",
                    1: "schedule",
                    2: "thermostat_input_no_1",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            ),
            "__termostatkierunek": CompitSelectDescription(
                key="__termostatkierunek",
                translation_key="r770rs_r771rs_thermostat_direction_1",
                icon="mdi:arrow-left-right",
                options_dict={
                    0: "opening_at_the_entrance_is_lowering",
                    1: "a_short_circuit_at_the_input_is_a_decrease",
                },
            ),
            "__trybpompymiesz2": CompitSelectDescription(
                key="__trybpompymiesz2",
                translation_key="r770rs_r771rs_disable_thermostatic_co2_pump",
                icon="mdi:thermostat",
                options_dict={
                    0: "continuous_operation",
                    1: "switched_off_by_thermostat",
                },
            ),
            "__trybmie2": CompitSelectDescription(
                key="__trybmie2",
                translation_key="r770rs_r771rs_lowering_source_mixer2",
                icon="mdi:mixer",
                options_dict={
                    0: "lack",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            ),
            "__termostatkierunek2": CompitSelectDescription(
                key="__termostatkierunek2",
                translation_key="r770rs_r771rs_thermostat_direction_2",
                icon="mdi:thermostat",
                options_dict={
                    0: "the_opening_at_the_input_is_a_signal_of_lowering",
                    1: "a_short_circuit_at_the_input_is_a_drop_signal",
                },
            ),
            "__trybpracycwu": CompitSelectDescription(
                key="__trybpracycwu",
                translation_key="r770rs_r771rs_dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    0: "circuit_off",
                    1: "work_comfort",
                    2: "working_with_the_clock",
                },
            ),
            "__trybpracycyrkcwu": CompitSelectDescription(
                key="__trybpracycyrkcwu",
                translation_key="r770rs_r771rs_dhw_circulation_operating_mode",
                icon="mdi:water-pump",
                options_dict={
                    0: "circuit_off",
                    1: "work_comfort",
                    2: "working_with_the_clock",
                },
            ),
            "__typkotla": CompitSelectDescription(
                key="__typkotla",
                translation_key="r770rs_r771rs_boiler_type",
                icon="mdi:fire",
                options_dict={
                    0: "other",
                    1: "kdc_eco_15",
                    2: "kdc_eco_20",
                    3: "kdc_eco_25",
                    4: "kdc_eco_35",
                    5: "kdc_eco_50",
                },
            ),
            "__ochronapodajnika": CompitSelectDescription(
                key="__ochronapodajnika",
                translation_key="r770rs_r771rs_feeder_protection",
                icon="mdi:shield-outline",
                options_dict={
                    0: "disabled",
                    1: "attached",
                },
            ),
            "__funkcpompypcyrk": CompitSelectDescription(
                key="__funkcpompypcyrk",
                translation_key="r770rs_r771rs_pump_function_p_circus",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "attached",
                    2: "hot_water_circulation",
                    3: "by_pass",
                },
            ),
            "__trybwc14": CompitSelectDescription(
                key="__trybwc14",
                translation_key="r770rs_r771rs_network_mode_c14",
                icon="mdi:lan",
                options_dict={
                    0: "subordinate",
                    1: "master",
                },
            ),
            "__trybzimalato": CompitSelectDescription(
                key="__trybzimalato",
                translation_key="r770rs_r771rs_winter_summer_mode",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                },
            ),
        },
        _class=25,
    ),
    14: CompitDeviceDescription(
        name="Regulator zaworu mieszajicego BWC310",
        parameters={
            "__pracamieszacza": CompitSelectDescription(
                key="__pracamieszacza",
                translation_key="regulator_zaworu_mieszajicego_bwc310_mixer_operation",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "nano_1",
                    5: "nano_2",
                    6: "nano_3",
                    7: "nano_4",
                    8: "nano_5",
                },
            ),
            "__kierunekdzialaniazaworu": CompitSelectDescription(
                key="__kierunekdzialaniazaworu",
                translation_key="regulator_zaworu_mieszajicego_bwc310_valve_direction",
                icon="mdi:valve-closed",
                options_dict={
                    0: "normal",
                    1: "inverted",
                },
            ),
            "__factoryreset": CompitSelectDescription(
                key="__factoryreset",
                translation_key="regulator_zaworu_mieszajicego_bwc310_restoring_factory_settings",
                icon="mdi:restore",
                options_dict={
                    0: "subordinate",
                    1: "master",
                },
            ),
        },
        _class=69,
    ),
    201: CompitDeviceDescription(
        name="BioMax775",
        parameters={
            "__pracakotla": CompitSelectDescription(
                key="__pracakotla",
                translation_key="biomax775_boiler_operation",
                icon="mdi:fire",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "with_nano_no_1",
                    5: "with_nano_no_2",
                    6: "with_nano_no_3_with_nano_no",
                    7: "with_nano_no_4",
                    8: "with_nano_no_5",
                },
            ),
            "__m1praca": CompitSelectDescription(
                key="__m1praca",
                translation_key="biomax775_mixer_1_work",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "z_nano_1",
                    5: "z_nano_2",
                    6: "with_nano_3",
                    7: "z_nano_4",
                    8: "z_nano_5",
                },
            ),
            "__m2praca": CompitSelectDescription(
                key="__m2praca",
                translation_key="biomax775_mixer_2_work",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "z_nano_1",
                    5: "z_nano_2",
                    6: "with_nano_3",
                    7: "z_nano_4",
                    8: "z_nano_5",
                },
            ),
            "__cwupraca": CompitSelectDescription(
                key="__cwupraca",
                translation_key="biomax775_dhw_work",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "comfortable",
                    2: "with_a_clock",
                },
            ),
            "__cwucyrkpraca": CompitSelectDescription(
                key="__cwucyrkpraca",
                translation_key="biomax775_dhw_circulation_work",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "with_a_clock",
                },
            ),
            "__trybwsiecic14": CompitSelectDescription(
                key="__trybwsiecic14",
                translation_key="biomax775_network_mode_c14",
                icon="mdi:lan",
                options_dict={
                    0: "slave",
                    1: "master",
                },
            ),
            "__typ instalacji": CompitSelectDescription(
                key="__typ instalacji",
                translation_key="biomax775_installation_type",
                icon="mdi:home-assistant",
                options_dict={
                    0: "pumping_system",
                    1: "buffer",
                    2: "remote_work",
                },
            ),
            "__czuloscklawiatury": CompitSelectDescription(
                key="__czuloscklawiatury",
                translation_key="biomax775_keyboard_sensitivity",
                icon="mdi:keyboard",
                options_dict={
                    0: "0",
                    1: "1",
                    2: "2",
                },
            ),
            "__kontrolapalnika": CompitSelectDescription(
                key="__kontrolapalnika",
                translation_key="biomax775_burner_control",
                icon="mdi:fire-circle",
                options_dict={
                    0: "disabled",
                    1: "defective_feeder_triac",
                    2: "no_feeder_operation",
                    3: "damaged_triac_and_no_work",
                },
            ),
        },
        _class=15,
    ),
    36: CompitDeviceDescription(
        name="BioMax742",
        parameters={
            "__pracakotla": CompitSelectDescription(
                key="__pracakotla",
                translation_key="biomax742_boiler_operation",
                icon="mdi:fire",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "with_nano_no_1",
                    5: "with_nano_no_2",
                    6: "with_nano_no_3",
                    7: "with_nano_no_4",
                    8: "with_nano_no_5",
                },
            ),
            "__m1praca": CompitSelectDescription(
                key="__m1praca",
                translation_key="biomax742_mixer_1_work",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "without",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "z_nano_1",
                    5: "z_nano_2",
                    6: "with_nano_3",
                    7: "z_nano_4",
                    8: "z_nano_5",
                },
            ),
            "__cwupraca": CompitSelectDescription(
                key="__cwupraca",
                translation_key="biomax742_dhw_work",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "comfortable",
                    2: "with_a_clock",
                },
            ),
            "__cwucyrkpraca": CompitSelectDescription(
                key="__cwucyrkpraca",
                translation_key="biomax742_dhw_circulation_work",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "with_a_clock",
                },
            ),
            "__typinstalacji": CompitSelectDescription(
                key="__typinstalacji",
                translation_key="biomax742_installation_type",
                icon="mdi:home-assistant",
                options_dict={
                    0: "pumping_system",
                    1: "buffer",
                    2: "remote_work",
                },
            ),
        },
        _class=15,
    ),
    75: CompitDeviceDescription(
        name="BioMax772",
        parameters={
            "__pracakotla": CompitSelectDescription(
                key="__pracakotla",
                translation_key="biomax772_boiler_operation",
                icon="mdi:fire",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "with_nano_no_1",
                    5: "with_nano_no_2",
                    6: "with_nano_no_3",
                    7: "with_nano_no_4",
                    8: "with_nano_no_5",
                },
            ),
            "__m1praca": CompitSelectDescription(
                key="__m1praca",
                translation_key="biomax772_mixer_1_work",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "z_nano_1",
                    5: "z_nano_2",
                    6: "with_nano_3",
                    7: "z_nano_4",
                    8: "z_nano_5",
                },
            ),
            "__m2praca": CompitSelectDescription(
                key="__m2praca",
                translation_key="biomax772_mixer_2_work",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "z_nano_1",
                    5: "z_nano_2",
                    6: "with_nano_3",
                    7: "z_nano_4",
                    8: "z_nano_5",
                },
            ),
            "__cwupraca": CompitSelectDescription(
                key="__cwupraca",
                translation_key="biomax772_dhw_work",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "comfortable",
                    2: "with_a_clock",
                },
            ),
            "__cwucyrkpraca": CompitSelectDescription(
                key="__cwucyrkpraca",
                translation_key="biomax772_dhw_circulation_work",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    3: "with_a_clock",
                },
            ),
            "__czuloscklawiatury": CompitSelectDescription(
                key="__czuloscklawiatury",
                translation_key="biomax772_keyboard_sensitivity",
                icon="mdi:keyboard",
                options_dict={
                    0: "0",
                    1: "1",
                    2: "2",
                },
            ),
        },
        _class=15,
    ),
    210: CompitDeviceDescription(
        name="EL750",
        parameters={
            "__tryblato": CompitSelectDescription(
                key="__tryblato",
                translation_key="el750_winter_summer",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                },
            ),
            "__trybcyrkulacji": CompitSelectDescription(
                key="__trybcyrkulacji",
                translation_key="el750_dhw_circulation_mode",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "comfort",
                    2: "with_a_clock",
                },
            ),
        },
        _class=29,
    ),
    221: CompitDeviceDescription(
        name="R350.M",
        parameters={
            "__tr_pr": CompitSelectDescription(
                key="__tr_pr",
                translation_key="r350_m_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    1: "no_corrections",
                    2: "with_a_clock",
                    3: "with_thermostat",
                    4: "with_nano_no_1_with_nano_no",
                    5: "with_nano_no_2",
                    6: "with_nano_no_3",
                    7: "with_nano_no_4",
                    8: "with_nano_no_5",
                },
            ),
            "__stop_min": CompitSelectDescription(
                key="__stop_min",
                translation_key="r350_m_stop_min",
                icon="mdi:stop-circle-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__stop_obn": CompitSelectDescription(
                key="__stop_obn",
                translation_key="r350_m_stop_obn",
                icon="mdi:stop-circle-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__sez_z_nano": CompitSelectDescription(
                key="__sez_z_nano",
                translation_key="r350_m_season_with_nano",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__stop_z_kot": CompitSelectDescription(
                key="__stop_z_kot",
                translation_key="r350_m_alloy_from_the_boiler",
                icon="mdi:fire",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__pog": CompitSelectDescription(
                key="__pog",
                translation_key="r350_m_weather",
                icon="mdi:weather-partly-cloudy",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__rodz_zaw": CompitSelectDescription(
                key="__rodz_zaw",
                translation_key="r350_m_valve_type",
                icon="mdi:valve-closed",
                options_dict={
                    0: "2_way",
                    1: "3_way",
                    2: "4_way",
                },
            ),
            "__tr_ochr": CompitSelectDescription(
                key="__tr_ochr",
                translation_key="r350_m_protection_mode",
                icon="mdi:shield-outline",
                options_dict={
                    0: "min",
                    1: "max",
                    2: "inactive",
                    3: "buffer",
                },
            ),
            "__cz_ochr": CompitSelectDescription(
                key="__cz_ochr",
                translation_key="r350_m_protection_sensor",
                icon="mdi:thermometer",
                options_dict={
                    0: "own",
                    1: "external",
                },
            ),
            "__t_kon_sez": CompitSelectDescription(
                key="__t_kon_sez",
                translation_key="r350_m_end_of_season_temperature",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "standard",
                    1: "average",
                },
            ),
            "__schemat": CompitSelectDescription(
                key="__schemat",
                translation_key="r350_m_schema",
                icon="mdi:floor-plan",
                options_dict={
                    0: "mixer",
                    1: "pump",
                },
            ),
            "__pr_w_c14": CompitSelectDescription(
                key="__pr_w_c14",
                translation_key="r350_m_work_in_the_c14_network",
                icon="mdi:lan",
                options_dict={
                    0: "subordinate",
                    1: "master",
                },
            ),
        },
        _class=14,
    ),
    5: CompitDeviceDescription(
        name="R350 T3",
        parameters={
            "__tryblato": CompitSelectDescription(
                key="__tryblato",
                translation_key="r350_t3_summer_winter_jobs",
                icon="mdi:cog-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                },
            ),
            "__pracamieszacza": CompitSelectDescription(
                key="__pracamieszacza",
                translation_key="r350_t3_work",
                icon="mdi:cog-outline",
                options_dict={
                    0: "no_corrections",
                    1: "with_a_clock",
                    2: "with_thermostat",
                    3: "with_nano_no_1",
                    4: "with_nano_no_2_nano",
                    5: "with_nano_no_3_nano",
                    6: "with_nano_no_4",
                    7: "with_nano_no_5",
                },
            ),
            "__zezwoleniezalpompyco": CompitSelectDescription(
                key="__zezwoleniezalpompyco",
                translation_key="r350_t3_stop_min",
                icon="mdi:stop-circle-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__pompacooffodnano": CompitSelectDescription(
                key="__pompacooffodnano",
                translation_key="r350_t3_stop_obn",
                icon="mdi:stop-circle-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__StopZkot": CompitSelectDescription(
                key="__StopZkot",
                translation_key="r350_t3_stopzkot",
                icon="mdi:stop-circle-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__pracawgharmonogramu": CompitSelectDescription(
                key="__pracawgharmonogramu",
                translation_key="r350_t3_work_according_to_the_schedule",
                icon="mdi:cog-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__praca_pogodowa": CompitSelectDescription(
                key="__praca_pogodowa",
                translation_key="r350_t3_weather_weather_work",
                icon="mdi:weather-partly-cloudy",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__rodzdetsezongrzew": CompitSelectDescription(
                key="__rodzdetsezongrzew",
                translation_key="r350_t3_tseason",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "standard",
                    1: "average",
                },
            ),
            "__pracaharmonogramu": CompitSelectDescription(
                key="__pracaharmonogramu",
                translation_key="r350_t3_work_according_to_the_schedule",
                icon="mdi:cog-outline",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
            "__pracapogodowa": CompitSelectDescription(
                key="__pracapogodowa",
                translation_key="r350_t3_weather_work",
                icon="mdi:weather-partly-cloudy",
                options_dict={
                    0: "no",
                    1: "tak",
                },
            ),
        },
        _class=14,
    ),
    215: CompitDeviceDescription(
        name="R480",
        parameters={
            "__serw_sys_tryb_w_sieci_c14": CompitSelectDescription(
                key="__serw_sys_tryb_w_sieci_c14",
                translation_key="r480_network_mode_c14",
                icon="mdi:lan",
                options_dict={
                    0: "slave",
                    1: "master",
                    2: "master_mini",
                },
            ),
            "__serw_sys_przyjm_tryb_pr_inst_z_nano1_wym_cwu": CompitSelectDescription(
                key="__serw_sys_przyjm_tryb_pr_inst_z_nano1_wym_cwu",
                translation_key="r480_taking_the_settings_from_nano1_forcing_dhw",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "attached",
                },
            ),
            "__buf_praca_w_tr_lato": CompitSelectDescription(
                key="__buf_praca_w_tr_lato",
                translation_key="r480_buffer_operation_in_summer_mode",
                icon="mdi:database",
                options_dict={
                    0: "disabled",
                    1: "attached",
                },
            ),
            "__cwu_cyrkulacja": CompitSelectDescription(
                key="__cwu_cyrkulacja",
                translation_key="r480_hot_water_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "in_clock_zones_in_zones",
                    2: "constant",
                },
            ),
            "__cwu_dzien_real_antylegion": CompitSelectDescription(
                key="__cwu_dzien_real_antylegion",
                translation_key="r480_day_of_the_week_for_the_implementation_of_anti_legionella",
                icon="mdi:calendar-week",
                options_dict={
                    0: "monday",
                    1: "tuesday",
                    2: "wednesday",
                    3: "thursday",
                    4: "friday",
                    5: "saturday",
                    6: "sunday",
                },
            ),
            "__praca_pc": CompitSelectDescription(
                key="__praca_pc",
                translation_key="r480_heat_pump_operation",
                icon="mdi:heat-pump",
                options_dict={
                    0: "stop",
                    1: "echo",
                    2: "hybrid",
                },
            ),
            "__tryb_instal": CompitSelectDescription(
                key="__tryb_instal",
                translation_key="r480_installation_mode_season",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "winter",
                    1: "side",
                },
            ),
            "__tryb_cwu": CompitSelectDescription(
                key="__tryb_cwu",
                translation_key="r480_hot_water_operation",
                icon="mdi:water-boiler",
                options_dict={
                    1: "car",
                    2: "manual",
                    0: "stop",
                },
            ),
            "__tr_buf": CompitSelectDescription(
                key="__tr_buf",
                translation_key="r480_buffer_operation",
                icon="mdi:database",
                options_dict={
                    1: "car",
                    2: "manual",
                    0: "stop",
                },
            ),
        },
        _class=43,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit select entities from a config entry."""

    coordinator = entry.runtime_data
    select_entities = []
    for device_id, device in coordinator.connector.all_devices.items():
        device_definition = DEVICE_DEFINITIONS.get(device.definition.code)

        if device_definition:
            for code, description in device_definition.parameters.items():
                param = next((p for p in device.state.params if p.code == code), None)

                if (
                    param is not None and not param.hidden
                ):  # Only add if parameter is not hidden
                    select_entities.append(
                        CompitSelect(
                            coordinator,
                            device_id,
                            device_definition.name,
                            code,
                            description,
                        )
                    )

    async_add_devices(select_entities)


class CompitSelect(CoordinatorEntity[CompitDataUpdateCoordinator], SelectEntity):
    """Representation of a Compit select entity."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        device_name: str,
        parameter_code: str,
        parameter_description: CompitSelectDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = parameter_description
        self._attr_unique_id = f"{device_id}_{parameter_code}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
        )
        self.parameter_code = parameter_code
        self.available_values = parameter_description.options_dict
        self._attr_options = list(parameter_description.options_dict.values())

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.connector.get_device(self.device_id) is not None
        )

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        param = self.coordinator.connector.get_device_parameter(
            self.device_id, self.parameter_code
        )
        if param is None or param.value is None:
            return None

        return self.available_values.get(param.value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        if option not in self.available_values.values():
            raise HomeAssistantError(f"Invalid option '{option}' for {self._attr_name}")

        for state_value, state_option in self.available_values.items():
            if state_option == option:
                await self.coordinator.connector.set_device_parameter(
                    self.device_id, self.parameter_code, state_value
                )
                self.async_write_ha_state()
                break
