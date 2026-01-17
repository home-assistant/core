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
            "__język": CompitSelectDescription(
                key="__język",
                translation_key="language",
                icon="mdi:translate",
                options_dict={
                    0: "polish",
                    1: "english",
                },
            ),
            "__aerokonfbypass": CompitSelectDescription(
                key="__aerokonfbypass",
                translation_key="aero_by_pass",
                icon="mdi:valve",
                options_dict={
                    0: "off",
                    1: "auto",
                    2: "on",
                },
            ),
            "__trybaero2": CompitSelectDescription(
                key="__trybaero2",
                translation_key="additional_ventilation_circuit",
                icon="mdi:fan",
                options_dict={
                    0: "gear_0",
                    1: "gear_1",
                    2: "gear_2",
                    3: "gear_3",
                    4: "gear_4",
                },
            ),
        },
    ),
    12: CompitDeviceDescription(
        name="Nano Color",
        parameters={
            "__język": CompitSelectDescription(
                key="__język",
                translation_key="language",
                icon="mdi:translate",
                options_dict={
                    0: "polish",
                    1: "english",
                },
            ),
            "__aerokonfbypass": CompitSelectDescription(
                key="__aerokonfbypass",
                translation_key="aero_by_pass",
                icon="mdi:valve",
                options_dict={
                    0: "off",
                    1: "auto",
                    2: "on",
                },
            ),
            "__trybaero2": CompitSelectDescription(
                key="__trybaero2",
                translation_key="additional_ventilation_circuit",
                icon="mdi:fan",
                options_dict={
                    0: "gear_0",
                    1: "gear_1",
                    2: "gear_2",
                    3: "gear_3",
                    4: "gear_4",
                },
            ),
        },
    ),
    7: CompitDeviceDescription(
        name="Nano One",
        parameters={
            "_jezyk": CompitSelectDescription(
                key="_jezyk",
                translation_key="language",
                icon="mdi:translate",
                options_dict={
                    0: "polish",
                    1: "english",
                },
            ),
            "__nano_mode": CompitSelectDescription(
                key="__nano_mode",
                translation_key="nano_work_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "manual_run_3",
                    1: "manual_run_2",
                    2: "manual_run_1",
                    3: "manual_run_0",
                    4: "schedule",
                    5: "christmas",
                    6: "out_of_home",
                },
            ),
            "__wentkomfort": CompitSelectDescription(
                key="__wentkomfort",
                translation_key="ventilation_in_the_comfort_zone",
                icon="mdi:fan",
                options_dict={
                    0: "gear_0",
                    1: "gear_1",
                    2: "gear_2",
                    3: "gear_3",
                },
            ),
            "__wenteko": CompitSelectDescription(
                key="__wenteko",
                translation_key="ventilation_in_the_eco_zone",
                icon="mdi:fan",
                options_dict={
                    0: "gear_0",
                    1: "gear_1",
                    2: "gear_2",
                    3: "gear_3",
                },
            ),
            "__wenturlop": CompitSelectDescription(
                key="__wenturlop",
                translation_key="ventilation_in_the_away_mode",
                icon="mdi:fan",
                options_dict={
                    0: "gear_0",
                    1: "gear_1",
                    2: "gear_2",
                    3: "gear_3",
                },
            ),
            "__a3programwietrzenia": CompitSelectDescription(
                key="__a3programwietrzenia",
                translation_key="airing_program_zone",
                icon="mdi:calendar-clock",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work30m_stop",
                    2: "20m_work40m_stop",
                    3: "20m_work100m_stop",
                },
                translation_placeholders={"zone": "3"},
            ),
            "__a3konfignagwst": CompitSelectDescription(
                key="__a3konfignagwst",
                translation_key="pre_heater_configuration_zone",
                icon="mdi:radiator",
                options_dict={
                    0: "disabled",
                    1: "onoff",
                    2: "pwm",
                },
                translation_placeholders={"zone": "3"},
            ),
            "__a3konfignagwt": CompitSelectDescription(
                key="__a3konfignagwt",
                translation_key="secondary_heater_configuration_zone",
                icon="mdi:radiator",
                options_dict={
                    0: "disabled",
                    1: "onoff_room_temp",
                    2: "onoff_outside_temp",
                    3: "onoff",
                    4: "pwm_room_temp",
                    5: "pwm_outside_temp",
                },
                translation_placeholders={"zone": "3"},
            ),
            "__a4programwietrzenia": CompitSelectDescription(
                key="__a4programwietrzenia",
                translation_key="airing_program_zone",
                icon="mdi:calendar-clock",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work30m_stop",
                    2: "20m_work40m_stop",
                    3: "20m_work100m_stop",
                },
                translation_placeholders={"zone": "4"},
            ),
            "__a5prwietrz": CompitSelectDescription(
                key="__a5prwietrz",
                translation_key="airing_program_zone",
                icon="mdi:fan",
                options_dict={
                    0: "no_exclusions",
                    1: "30m_work30m_stop",
                    2: "20m_work40m_stop",
                    3: "20m_work100m_stop",
                },
                translation_placeholders={"zone": "5"},
            ),
            "__a5trybnagrzwst": CompitSelectDescription(
                key="__a5trybnagrzwst",
                translation_key="pre_heater_configuration_zone",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "onoff",
                    2: "pwm",
                },
                translation_placeholders={"zone": "5"},
            ),
            "__a5trnagrzgl": CompitSelectDescription(
                key="__a5trnagrzgl",
                translation_key="secondary_heater_configuration_zone",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "pwm",
                },
                translation_placeholders={"zone": "5"},
            ),
        },
    ),
    224: CompitDeviceDescription(
        name="R 900",
        parameters={
            "__typ_obwo_co1": CompitSelectDescription(
                key="__typ_obwo_co1",
                translation_key="circuit_type_heating_zone",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
                translation_placeholders={"zone": "1"},
            ),
            "__typ_obwo_co2": CompitSelectDescription(
                key="__typ_obwo_co2",
                translation_key="circuit_type_heating_zone",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
                translation_placeholders={"zone": "2"},
            ),
            "__typ_obwo_co3": CompitSelectDescription(
                key="__typ_obwo_co3",
                translation_key="circuit_type_heating_zone",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
                translation_placeholders={"zone": "3"},
            ),
            "__typ_obwo_co4": CompitSelectDescription(
                key="__typ_obwo_co4",
                translation_key="circuit_type_heating_zone",
                icon="mdi:pipe",
                options_dict={
                    0: "pump",
                    1: "mixer",
                },
                translation_placeholders={"zone": "4"},
            ),
            "__cyrk_cwu": CompitSelectDescription(
                key="__cyrk_cwu",
                translation_key="hot_water_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "constant",
                },
            ),
            "__tr_pracy_pc": CompitSelectDescription(
                key="__tr_pracy_pc",
                translation_key="operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "eco",
                    2: "hybrid",
                },
            ),
            "__tr_pr_co1": CompitSelectDescription(
                key="__tr_pr_co1",
                translation_key="heating_operating_mode_zone",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "1"},
            ),
            "__tr_pr_co2": CompitSelectDescription(
                key="__tr_pr_co2",
                translation_key="heating_operating_mode_zone",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "2"},
            ),
            "__tr_pr_co3": CompitSelectDescription(
                key="__tr_pr_co3",
                translation_key="heating_operating_mode_zone",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "3"},
            ),
            "__tr_pr_co4": CompitSelectDescription(
                key="__tr_pr_co4",
                translation_key="heating_operating_mode_zone",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "4"},
            ),
        },
    ),
    3: CompitDeviceDescription(
        name="R810",
        parameters={
            "__pracamieszacza": CompitSelectDescription(
                key="__pracamieszacza",
                translation_key="mixer_mode",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "with_a_schedule",
                    3: "with_thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
        },
    ),
    45: CompitDeviceDescription(
        name="SolarComp971",
        parameters={
            "__trybpracy": CompitSelectDescription(
                key="__trybpracy",
                translation_key="solarcomp_operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    1: "auto",
                    2: "de_icing",
                    3: "holiday",
                    4: "disabled",
                },
            ),
        },
    ),
    44: CompitDeviceDescription(
        name="SolarComp 951",
        parameters={
            "__trybpracy": CompitSelectDescription(
                key="__trybpracy",
                translation_key="solarcomp_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    1: "auto",
                    2: "de_icing",
                    3: "holiday",
                    4: "disabled",
                },
            ),
        },
    ),
    92: CompitDeviceDescription(
        name="r490",
        parameters={
            "__co1zrodlokorekty": CompitSelectDescription(
                key="__co1zrodlokorekty",
                translation_key="heating_source_of_correction_zone",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
                translation_placeholders={"zone": "1"},
            ),
            "_co2zrodlokorekty": CompitSelectDescription(
                key="_co2zrodlokorekty",
                translation_key="heating_source_of_correction_zone",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
                translation_placeholders={"zone": "2"},
            ),
            "__co3zrodlokorekty": CompitSelectDescription(
                key="__co3zrodlokorekty",
                translation_key="heating_source_of_correction_zone",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
                translation_placeholders={"zone": "3"},
            ),
            "__co4zrkorekty": CompitSelectDescription(
                key="__co4zrkorekty",
                translation_key="heating_source_of_correction_zone",
                icon="mdi:tune-variant",
                options_dict={
                    0: "no_corrections",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
                translation_placeholders={"zone": "4"},
            ),
            "__sezprinst": CompitSelectDescription(
                key="__sezprinst",
                translation_key="operating_mode",
                icon="mdi:home-thermometer-outline",
                options_dict={
                    0: "disabled",
                    1: "eco",
                    2: "hybrid",
                },
            ),
            "__trybprcwu": CompitSelectDescription(
                key="__trybprcwu",
                translation_key="dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    1: "schedule",
                    2: "manual",
                },
            ),
            "__trprco1": CompitSelectDescription(
                key="__trprco1",
                translation_key="heating_operating_mode_zone",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "1"},
            ),
            "__trprco2": CompitSelectDescription(
                key="__trprco2",
                translation_key="heating_operating_mode_zone",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "2"},
            ),
            "__trprco3": CompitSelectDescription(
                key="__trprco3",
                translation_key="heating_operating_mode_zone",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "3"},
            ),
            "__trprco4": CompitSelectDescription(
                key="__trprco4",
                translation_key="heating_operating_mode_zone",
                icon="mdi:cog-outline",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
                translation_placeholders={"zone": "4"},
            ),
            "__trprbufora": CompitSelectDescription(
                key="__trprbufora",
                translation_key="buffer_mode",
                icon="mdi:database",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "manual",
                },
            ),
        },
    ),
    34: CompitDeviceDescription(
        name="r470",
        parameters={
            "__mode": CompitSelectDescription(
                key="__mode",
                translation_key="operating_mode",
                icon="mdi:cog-outline",
                options_dict={
                    1: "disabled",
                    2: "auto",
                    3: "eco",
                },
            ),
            "__comode": CompitSelectDescription(
                key="__comode",
                translation_key="heating_source_of_correction",
                icon="mdi:cog-outline",
                options_dict={
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__mixer1mode": CompitSelectDescription(
                key="__mixer1mode",
                translation_key="mixer_mode",
                icon="mdi:mixer",
                options_dict={
                    1: "no_corrections",
                    2: "clock",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__dhwmode": CompitSelectDescription(
                key="__dhwmode",
                translation_key="dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
            "__dhwcircmode": CompitSelectDescription(
                key="__dhwcircmode",
                translation_key="dhw_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
        },
    ),
    91: CompitDeviceDescription(
        name="R770RS / R771RS",
        parameters={
            "__trybmieszacza": CompitSelectDescription(
                key="__trybmieszacza",
                translation_key="mixer_mode",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            ),
            "__trybmie2": CompitSelectDescription(
                key="__trybmie2",
                translation_key="mixer_mode",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            ),
            "__trybpracycwu": CompitSelectDescription(
                key="__trybpracycwu",
                translation_key="dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
            "__trybpracycyrkcwu": CompitSelectDescription(
                key="__trybpracycyrkcwu",
                translation_key="hot_water_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
        },
    ),
    14: CompitDeviceDescription(
        name="BWC310",
        parameters={
            "__pracamieszacza": CompitSelectDescription(
                key="__pracamieszacza",
                translation_key="mixer_mode",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            )
        },
    ),
    201: CompitDeviceDescription(
        name="BioMax775",
        parameters={
            "__pracakotla": CompitSelectDescription(
                key="__pracakotla",
                translation_key="heating_source_of_correction_zone",
                icon="mdi:fire",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__m1praca": CompitSelectDescription(
                key="__m1praca",
                translation_key="mixer_mode_zone",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
                translation_placeholders={"zone": "1"},
            ),
            "__m2praca": CompitSelectDescription(
                key="__m2praca",
                translation_key="mixer_mode_zone",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "without_thermostat",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
                translation_placeholders={"zone": "2"},
            ),
            "__cwupraca": CompitSelectDescription(
                key="__cwupraca",
                translation_key="dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
            "__cwucyrkpraca": CompitSelectDescription(
                key="__cwucyrkpraca",
                translation_key="dhw_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
        },
    ),
    36: CompitDeviceDescription(
        name="BioMax742",
        parameters={
            "__pracakotla": CompitSelectDescription(
                key="__pracakotla",
                translation_key="heating_source_of_correction_zone",
                icon="mdi:fire",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__m1praca": CompitSelectDescription(
                key="__m1praca",
                translation_key="mixer_mode",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__cwupraca": CompitSelectDescription(
                key="__cwupraca",
                translation_key="dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
            "__cwucyrkpraca": CompitSelectDescription(
                key="__cwucyrkpraca",
                translation_key="dhw_circulation_work",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
        },
    ),
    75: CompitDeviceDescription(
        name="BioMax772",
        parameters={
            "__pracakotla": CompitSelectDescription(
                key="__pracakotla",
                translation_key="heating_source_of_correction_zone",
                icon="mdi:fire",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__m1praca": CompitSelectDescription(
                key="__m1praca",
                translation_key="mixer_mode_zone",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__m2praca": CompitSelectDescription(
                key="__m2praca",
                translation_key="mixer_mode_zone",
                icon="mdi:mixer",
                options_dict={
                    0: "disabled",
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
            "__cwupraca": CompitSelectDescription(
                key="__cwupraca",
                translation_key="dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
            "__cwucyrkpraca": CompitSelectDescription(
                key="__cwucyrkpraca",
                translation_key="dhw_circulation_work",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
                },
            ),
        },
    ),
    210: CompitDeviceDescription(
        name="EL750",
        parameters={
            "__trybcyrkulacji": CompitSelectDescription(
                key="__trybcyrkulacji",
                translation_key="dhw_circulation_work",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "constant",
                    2: "schedule",
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
                translation_key="heating_source_of_correction_zone",
                icon="mdi:cog-outline",
                options_dict={
                    1: "no_corrections",
                    2: "schedule",
                    3: "thermostat",
                    4: "nano_nr_1",
                    5: "nano_nr_2",
                    6: "nano_nr_3",
                    7: "nano_nr_4",
                    8: "nano_nr_5",
                },
            ),
        },
    ),
    5: CompitDeviceDescription(
        name="R350 T3",
        parameters={
            "__pracamieszacza": CompitSelectDescription(
                key="__pracamieszacza",
                translation_key="mixer_mode",
                icon="mdi:cog-outline",
                options_dict={
                    0: "no_corrections",
                    1: "schedule",
                    2: "thermostat",
                    3: "nano_nr_1",
                    4: "nano_nr_2",
                    5: "nano_nr_3",
                    6: "nano_nr_4",
                    7: "nano_nr_5",
                },
            )
        },
        _class=14,
    ),
    215: CompitDeviceDescription(
        name="R480",
        parameters={
            "__cwu_cyrkulacja": CompitSelectDescription(
                key="__cwu_cyrkulacja",
                translation_key="dhw_circulation",
                icon="mdi:water-pump",
                options_dict={
                    0: "disabled",
                    1: "schedule",
                    2: "constant",
                },
            ),
            "__praca_pc": CompitSelectDescription(
                key="__praca_pc",
                translation_key="operating_mode",
                icon="mdi:heat-pump",
                options_dict={
                    0: "disabled",
                    1: "eco",
                    2: "hybrid",
                },
            ),
            "__tryb_cwu": CompitSelectDescription(
                key="__tryb_cwu",
                translation_key="dhw_operating_mode",
                icon="mdi:water-boiler",
                options_dict={
                    1: "schedule",
                    2: "manual",
                    0: "disabled",
                },
            ),
            "__tr_buf": CompitSelectDescription(
                key="__tr_buf",
                translation_key="buffer_mode",
                icon="mdi:database",
                options_dict={
                    1: "schedule",
                    2: "manual",
                    0: "disabled",
                },
            ),
        },
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
