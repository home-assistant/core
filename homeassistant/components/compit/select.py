"""Select platform for Compit integration."""

from dataclasses import dataclass

from compit_inext_api.consts import CompitParameter

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

SELECT_PARAM_TYPE = "Select"
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CompitDeviceDescription:
    """Class to describe a Compit device."""

    name: str
    """Name of the device."""

    parameters: dict[CompitParameter, SelectEntityDescription]
    """Parameters of the device."""


DEVICE_DEFINITIONS: dict[int, CompitDeviceDescription] = {
    223: CompitDeviceDescription(
        name="Nano Color 2",
        parameters={
            CompitParameter.LANGUAGE: SelectEntityDescription(
                key=CompitParameter.LANGUAGE.value,
                translation_key="language",
                options=[
                    "polish",
                    "english",
                ],
            ),
            CompitParameter.AEROKONFBYPASS: SelectEntityDescription(
                key=CompitParameter.AEROKONFBYPASS.value,
                translation_key="aero_by_pass",
                options=[
                    "off",
                    "auto",
                    "on",
                ],
            ),
        },
    ),
    12: CompitDeviceDescription(
        name="Nano Color",
        parameters={
            CompitParameter.LANGUAGE: SelectEntityDescription(
                key=CompitParameter.LANGUAGE.value,
                translation_key="language",
                options=[
                    "polish",
                    "english",
                ],
            ),
            CompitParameter.AEROKONFBYPASS: SelectEntityDescription(
                key=CompitParameter.AEROKONFBYPASS.value,
                translation_key="aero_by_pass",
                options=[
                    "off",
                    "auto",
                    "on",
                ],
            ),
        },
    ),
    7: CompitDeviceDescription(
        name="Nano One",
        parameters={
            CompitParameter.LANGUAGE: SelectEntityDescription(
                key=CompitParameter.LANGUAGE.value,
                translation_key="language",
                options=[
                    "polish",
                    "english",
                ],
            ),
            CompitParameter.NANO_MODE: SelectEntityDescription(
                key=CompitParameter.NANO_MODE.value,
                translation_key="nano_work_mode",
                options=[
                    "manual_3",
                    "manual_2",
                    "manual_1",
                    "manual_0",
                    "schedule",
                    "christmas",
                    "out_of_home",
                ],
            ),
            CompitParameter.AIRING_PROGRAM_ZONE_3: SelectEntityDescription(
                key=CompitParameter.AIRING_PROGRAM_ZONE_3.value,
                translation_key="airing_program_zone",
                options=[
                    "no_exclusions",
                    "30m_work30m_stop",
                    "20m_work40m_stop",
                    "20m_work100m_stop",
                ],
                translation_placeholders={"zone": "3"},
            ),
            CompitParameter.PRE_HEATER_ZONE_3: SelectEntityDescription(
                key=CompitParameter.PRE_HEATER_ZONE_3.value,
                translation_key="pre_heater_configuration_zone",
                options=[
                    "disabled",
                    "onoff",
                    "pwm",
                ],
                translation_placeholders={"zone": "3"},
            ),
            CompitParameter.SECONDARY_HEATER_ZONE_3: SelectEntityDescription(
                key=CompitParameter.SECONDARY_HEATER_ZONE_3.value,
                translation_key="secondary_heater_configuration_zone",
                options=[
                    "disabled",
                    "onoff_room_temp",
                    "onoff_outside_temp",
                    "onoff",
                    "pwm_room_temp",
                    "pwm_outside_temp",
                ],
                translation_placeholders={"zone": "3"},
            ),
            CompitParameter.AIRING_PROGRAM_ZONE_4: SelectEntityDescription(
                key=CompitParameter.AIRING_PROGRAM_ZONE_4.value,
                translation_key="airing_program_zone",
                options=[
                    "no_exclusions",
                    "30m_work30m_stop",
                    "20m_work40m_stop",
                    "20m_work100m_stop",
                ],
                translation_placeholders={"zone": "4"},
            ),
            CompitParameter.AIRING_PROGRAM_ZONE_5: SelectEntityDescription(
                key=CompitParameter.AIRING_PROGRAM_ZONE_5.value,
                translation_key="airing_program_zone",
                options=[
                    "no_exclusions",
                    "30m_work30m_stop",
                    "20m_work40m_stop",
                    "20m_work100m_stop",
                ],
                translation_placeholders={"zone": "5"},
            ),
            CompitParameter.PRE_HEATER_ZONE_5: SelectEntityDescription(
                key=CompitParameter.PRE_HEATER_ZONE_5.value,
                translation_key="pre_heater_configuration_zone",
                options=[
                    "disabled",
                    "onoff",
                    "pwm",
                ],
                translation_placeholders={"zone": "5"},
            ),
            CompitParameter.SECONDARY_HEATER_ZONE_5: SelectEntityDescription(
                key=CompitParameter.SECONDARY_HEATER_ZONE_5.value,
                translation_key="secondary_heater_configuration_zone",
                options=[
                    "disabled",
                    "pwm",
                ],
                translation_placeholders={"zone": "5"},
            ),
        },
    ),
    224: CompitDeviceDescription(
        name="R 900",
        parameters={
            CompitParameter.CIRCUIT_MODE_HEATING_ZONE_1: SelectEntityDescription(
                key=CompitParameter.CIRCUIT_MODE_HEATING_ZONE_1.value,
                translation_key="circuit_type_heating_zone",
                options=[
                    "pump",
                    "mixer",
                ],
                translation_placeholders={"zone": "1"},
            ),
            CompitParameter.CIRCUIT_MODE_HEATING_ZONE_2: SelectEntityDescription(
                key=CompitParameter.CIRCUIT_MODE_HEATING_ZONE_2.value,
                translation_key="circuit_type_heating_zone",
                options=[
                    "pump",
                    "mixer",
                ],
                translation_placeholders={"zone": "2"},
            ),
            CompitParameter.CIRCUIT_MODE_HEATING_ZONE_3: SelectEntityDescription(
                key=CompitParameter.CIRCUIT_MODE_HEATING_ZONE_3.value,
                translation_key="circuit_type_heating_zone",
                options=[
                    "pump",
                    "mixer",
                ],
                translation_placeholders={"zone": "3"},
            ),
            CompitParameter.CIRCUIT_MODE_HEATING_ZONE_4: SelectEntityDescription(
                key=CompitParameter.CIRCUIT_MODE_HEATING_ZONE_4.value,
                translation_key="circuit_type_heating_zone",
                options=[
                    "pump",
                    "mixer",
                ],
                translation_placeholders={"zone": "4"},
            ),
            CompitParameter.DHWC_CIRCULATION: SelectEntityDescription(
                key=CompitParameter.DHWC_CIRCULATION.value,
                translation_key="hot_water_circulation",
                options=[
                    "disabled",
                    "schedule",
                    "constant",
                ],
            ),
            CompitParameter.OPERATING_MODE: SelectEntityDescription(
                key=CompitParameter.OPERATING_MODE.value,
                translation_key="operating_mode",
                options=[
                    "disabled",
                    "eco",
                    "hybrid",
                ],
            ),
            CompitParameter.HEATING_MODE_ZONE_1: SelectEntityDescription(
                key=CompitParameter.HEATING_MODE_ZONE_1.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "1"},
            ),
            CompitParameter.HEATING_MODE_ZONE_2: SelectEntityDescription(
                key=CompitParameter.HEATING_MODE_ZONE_2.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "2"},
            ),
            CompitParameter.HEATING_MODE_ZONE_3: SelectEntityDescription(
                key=CompitParameter.HEATING_MODE_ZONE_3.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "3"},
            ),
            CompitParameter.HEATING_MODE_ZONE_4: SelectEntityDescription(
                key=CompitParameter.HEATING_MODE_ZONE_4.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "4"},
            ),
        },
    ),
    3: CompitDeviceDescription(
        name="R810",
        parameters={
            CompitParameter.MIXER_MODE: SelectEntityDescription(
                key=CompitParameter.MIXER_MODE.value,
                translation_key="mixer_mode",
                options=[
                    "disabled",
                    "no_corrections",
                    "with_a_schedule",
                    "with_thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            ),
        },
    ),
    45: CompitDeviceDescription(
        name="SolarComp971",
        parameters={
            CompitParameter.SOLAR_COMP_OPERATING_MODE: SelectEntityDescription(
                key=CompitParameter.SOLAR_COMP_OPERATING_MODE.value,
                translation_key="solarcomp_operating_mode",
                options=[
                    "auto",
                    "de_icing",
                    "holiday",
                    "disabled",
                ],
            ),
        },
    ),
    44: CompitDeviceDescription(
        name="SolarComp 951",
        parameters={
            CompitParameter.SOLAR_COMP_OPERATING_MODE: SelectEntityDescription(
                key=CompitParameter.SOLAR_COMP_OPERATING_MODE.value,
                translation_key="solarcomp_operating_mode",
                options=[
                    "auto",
                    "de_icing",
                    "holiday",
                    "disabled",
                ],
            ),
        },
    ),
    92: CompitDeviceDescription(
        name="r490",
        parameters={
            CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_1: SelectEntityDescription(
                key=CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_1.value,
                translation_key="heating_source_of_correction_zone",
                options=[
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "1"},
            ),
            CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_2: SelectEntityDescription(
                key=CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_2.value,
                translation_key="heating_source_of_correction_zone",
                options=[
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "2"},
            ),
            CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_3: SelectEntityDescription(
                key=CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_3.value,
                translation_key="heating_source_of_correction_zone",
                options=[
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "3"},
            ),
            CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_4: SelectEntityDescription(
                key=CompitParameter.HEATING_SOURCE_OF_CORRECTION_ZONE_4.value,
                translation_key="heating_source_of_correction_zone",
                options=[
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "4"},
            ),
            CompitParameter.R490_OPERATING_MODE: SelectEntityDescription(
                key=CompitParameter.R490_OPERATING_MODE.value,
                translation_key="operating_mode",
                options=[
                    "disabled",
                    "eco",
                    "hybrid",
                ],
            ),
            CompitParameter.DHW_OPERATING_MODE: SelectEntityDescription(
                key=CompitParameter.DHW_OPERATING_MODE.value,
                translation_key="dhw_operating_mode",
                options=[
                    "schedule",
                    "manual",
                ],
            ),
            CompitParameter.HEATING_OPERATING_MODE_ZONE_1: SelectEntityDescription(
                key=CompitParameter.HEATING_OPERATING_MODE_ZONE_1.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "1"},
            ),
            CompitParameter.HEATING_OPERATING_MODE_ZONE_2: SelectEntityDescription(
                key=CompitParameter.HEATING_OPERATING_MODE_ZONE_2.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "2"},
            ),
            CompitParameter.HEATING_OPERATING_MODE_ZONE_3: SelectEntityDescription(
                key=CompitParameter.HEATING_OPERATING_MODE_ZONE_3.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "3"},
            ),
            CompitParameter.HEATING_OPERATING_MODE_ZONE_4: SelectEntityDescription(
                key=CompitParameter.HEATING_OPERATING_MODE_ZONE_4.value,
                translation_key="heating_operating_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
                translation_placeholders={"zone": "4"},
            ),
            CompitParameter.BUFFER_MODE: SelectEntityDescription(
                key=CompitParameter.BUFFER_MODE.value,
                translation_key="buffer_mode",
                options=[
                    "disabled",
                    "schedule",
                    "manual",
                ],
            ),
        },
    ),
    34: CompitDeviceDescription(
        name="r470",
        parameters={
            CompitParameter.R470_OPERATING_MODE: SelectEntityDescription(
                key=CompitParameter.R470_OPERATING_MODE.value,
                translation_key="operating_mode",
                options=[
                    "disabled",
                    "auto",
                    "eco",
                ],
            ),
            CompitParameter.HEATING_SOURCE_OF_CORRECTION: SelectEntityDescription(
                key=CompitParameter.HEATING_SOURCE_OF_CORRECTION.value,
                translation_key="heating_source_of_correction",
                options=[
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            ),
            CompitParameter.MIXERMODE_ZONE_1: SelectEntityDescription(
                key=CompitParameter.MIXERMODE_ZONE_1.value,
                translation_key="mixer_mode",
                options=[
                    "no_corrections",
                    "clock",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            ),
            CompitParameter.DHW_MODE: SelectEntityDescription(
                key=CompitParameter.DHW_MODE.value,
                translation_key="dhw_operating_mode",
                options=[
                    "disabled",
                    "constant",
                    "schedule",
                ],
            ),
            CompitParameter.DHW_CIRCULATION_MODE: SelectEntityDescription(
                key=CompitParameter.DHW_CIRCULATION_MODE.value,
                translation_key="dhw_circulation",
                options=[
                    "disabled",
                    "constant",
                    "schedule",
                ],
            ),
        },
    ),
    91: CompitDeviceDescription(
        name="R770RS / R771RS",
        parameters={
            CompitParameter.R770_MIXER_MODE_ZONE_1: SelectEntityDescription(
                key=CompitParameter.R770_MIXER_MODE_ZONE_1.value,
                translation_key="mixer_mode_zone",
                options=[
                    "disabled",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "1"},
            ),
            CompitParameter.R770_MIXER_MODE_ZONE_2: SelectEntityDescription(
                key=CompitParameter.R770_MIXER_MODE_ZONE_2.value,
                translation_key="mixer_mode",
                options=[
                    "disabled",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "2"},
            ),
            CompitParameter.R770_DHW_CIRCULATION_MODE: SelectEntityDescription(
                key=CompitParameter.R770_DHW_CIRCULATION_MODE.value,
                translation_key="dhw_circulation",
                options=[
                    "disabled",
                    "constant",
                    "schedule",
                ],
            ),
        },
    ),
    14: CompitDeviceDescription(
        name="BWC310",
        parameters={
            CompitParameter.MIXER_MODE: SelectEntityDescription(
                key=CompitParameter.MIXER_MODE.value,
                translation_key="mixer_mode",
                options=[
                    "disabled",
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            )
        },
    ),
    201: CompitDeviceDescription(
        name="BioMax775",
        parameters={
            CompitParameter.BIOMAX_HEATING_SOURCE_OF_CORRECTION: SelectEntityDescription(
                key=CompitParameter.BIOMAX_HEATING_SOURCE_OF_CORRECTION.value,
                translation_key="heating_source_of_correction",
                options=[
                    "disabled",
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            ),
            CompitParameter.BIOMAX_MIXER_MODE_ZONE_1: SelectEntityDescription(
                key=CompitParameter.BIOMAX_MIXER_MODE_ZONE_1.value,
                translation_key="mixer_mode_zone",
                options=[
                    "disabled",
                    "without_thermostat",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "1"},
            ),
            CompitParameter.BIOMAX_MIXER_MODE_ZONE_2: SelectEntityDescription(
                key=CompitParameter.BIOMAX_MIXER_MODE_ZONE_2.value,
                translation_key="mixer_mode_zone",
                options=[
                    "disabled",
                    "without_thermostat",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "2"},
            ),
            CompitParameter.BIOMAX_DHW_CIRCULATION_MODE: SelectEntityDescription(
                key=CompitParameter.BIOMAX_DHW_CIRCULATION_MODE.value,
                translation_key="dhw_circulation",
                options=[
                    "disabled",
                    "constant",
                    "schedule",
                ],
            ),
        },
    ),
    36: CompitDeviceDescription(
        name="BioMax742",
        parameters={
            CompitParameter.BIOMAX_HEATING_SOURCE_OF_CORRECTION: SelectEntityDescription(
                key=CompitParameter.BIOMAX_HEATING_SOURCE_OF_CORRECTION.value,
                translation_key="heating_source_of_correction",
                options=[
                    "disabled",
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            ),
            CompitParameter.BIOMAX_MIXER_MODE_ZONE_1: SelectEntityDescription(
                key=CompitParameter.BIOMAX_MIXER_MODE_ZONE_1.value,
                translation_key="mixer_mode",
                options=[
                    "disabled",
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            ),
            CompitParameter.BIOMAX_DHW_CIRCULATION_MODE: SelectEntityDescription(
                key=CompitParameter.BIOMAX_DHW_CIRCULATION_MODE.value,
                translation_key="dhw_circulation_work",
                options=[
                    "disabled",
                    "constant",
                    "schedule",
                ],
            ),
        },
    ),
    75: CompitDeviceDescription(
        name="BioMax772",
        parameters={
            CompitParameter.BIOMAX_HEATING_SOURCE_OF_CORRECTION: SelectEntityDescription(
                key=CompitParameter.BIOMAX_HEATING_SOURCE_OF_CORRECTION.value,
                translation_key="heating_source_of_correction",
                options=[
                    "disabled",
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            ),
            CompitParameter.BIOMAX_MIXER_MODE_ZONE_1: SelectEntityDescription(
                key=CompitParameter.BIOMAX_MIXER_MODE_ZONE_1.value,
                translation_key="mixer_mode_zone",
                options=[
                    "disabled",
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "1"},
            ),
            CompitParameter.BIOMAX_MIXER_MODE_ZONE_2: SelectEntityDescription(
                key=CompitParameter.BIOMAX_MIXER_MODE_ZONE_2.value,
                translation_key="mixer_mode_zone",
                options=[
                    "disabled",
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
                translation_placeholders={"zone": "2"},
            ),
            CompitParameter.BIOMAX_DHW_CIRCULATION_MODE: SelectEntityDescription(
                key=CompitParameter.BIOMAX_DHW_CIRCULATION_MODE.value,
                translation_key="dhw_circulation_work",
                options=[
                    "disabled",
                    "constant",
                    "schedule",
                ],
            ),
        },
    ),
    210: CompitDeviceDescription(
        name="EL750",
        parameters={
            CompitParameter.BIOMAX_CIRCULATION_MODE: SelectEntityDescription(
                key=CompitParameter.BIOMAX_CIRCULATION_MODE.value,
                translation_key="dhw_circulation_work",
                options=[
                    "disabled",
                    "constant",
                    "schedule",
                ],
            ),
        },
    ),
    5: CompitDeviceDescription(
        name="R350 T3",
        parameters={
            CompitParameter.MIXER_MODE: SelectEntityDescription(
                key=CompitParameter.MIXER_MODE.value,
                translation_key="mixer_mode",
                options=[
                    "no_corrections",
                    "schedule",
                    "thermostat",
                    "nano_nr_1",
                    "nano_nr_2",
                    "nano_nr_3",
                    "nano_nr_4",
                    "nano_nr_5",
                ],
            )
        },
    ),
    215: CompitDeviceDescription(
        name="R480",
        parameters={
            CompitParameter.R480_DHW_CIRCULATION: SelectEntityDescription(
                key=CompitParameter.R480_DHW_CIRCULATION.value,
                translation_key="dhw_circulation",
                options=[
                    "disabled",
                    "schedule",
                    "constant",
                ],
            ),
            CompitParameter.R480_OPERATING_MODE: SelectEntityDescription(
                key=CompitParameter.R480_OPERATING_MODE.value,
                translation_key="operating_mode",
                options=[
                    "disabled",
                    "eco",
                    "hybrid",
                ],
            ),
            CompitParameter.R480_BUFFER_MODE: SelectEntityDescription(
                key=CompitParameter.R480_BUFFER_MODE.value,
                translation_key="buffer_mode",
                options=[
                    "schedule",
                    "manual",
                    "disabled",
                ],
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

        if not device_definition:
            continue

        for code, entity_description in device_definition.parameters.items():
            param = next((p for p in device.state.params if p.code == code.value), None)

            if param is None:
                continue

            select_entities.append(
                CompitSelect(
                    coordinator,
                    device_id,
                    device_definition.name,
                    code,
                    entity_description,
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
        parameter_code: CompitParameter,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device_id}_{parameter_code.value}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
        )
        self.parameter_code = parameter_code

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
        return self.coordinator.connector.get_current_option(
            self.device_id, self.parameter_code
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.connector.select_device_option(
            self.device_id, self.parameter_code, option
        )
        self.async_write_ha_state()
