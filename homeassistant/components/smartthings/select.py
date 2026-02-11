"""Support for select entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity, SmartThingsFsvEntity

LAMP_TO_HA = {
    "extraHigh": "extra_high",
    "high": "high",
    "mid": "mid",
    "low": "low",
    "on": "on",
    "off": "off",
}

WASHER_SOIL_LEVEL_TO_HA = {
    "none": "none",
    "heavy": "heavy",
    "normal": "normal",
    "light": "light",
    "extraLight": "extra_light",
    "extraHeavy": "extra_heavy",
    "up": "up",
    "down": "down",
}

WASHER_SPIN_LEVEL_TO_HA = {
    "none": "none",
    "rinseHold": "rinse_hold",
    "noSpin": "no_spin",
    "low": "low",
    "extraLow": "extra_low",
    "delicate": "delicate",
    "medium": "medium",
    "high": "high",
    "extraHigh": "extra_high",
    "200": "200",
    "400": "400",
    "600": "600",
    "800": "800",
    "1000": "1000",
    "1200": "1200",
    "1400": "1400",
    "1600": "1600",
}

WASHER_WATER_TEMPERATURE_TO_HA = {
    "none": "none",
    "20": "20",
    "30": "30",
    "40": "40",
    "50": "50",
    "60": "60",
    "65": "65",
    "70": "70",
    "75": "75",
    "80": "80",
    "90": "90",
    "95": "95",
    "tapCold": "tap_cold",
    "cold": "cold",
    "cool": "cool",
    "ecoWarm": "eco_warm",
    "warm": "warm",
    "semiHot": "semi_hot",
    "hot": "hot",
    "extraHot": "extra_hot",
    "extraLow": "extra_low",
    "low": "low",
    "mediumLow": "medium_low",
    "medium": "medium",
    "high": "high",
}


@dataclass(frozen=True, kw_only=True)
class SmartThingsSelectDescription(SelectEntityDescription):
    """Class describing SmartThings select entities."""

    key: Capability
    requires_remote_control_status: bool = False
    options_attribute: Attribute
    status_attribute: Attribute
    command: Command
    options_map: dict[str, str] | None = None
    default_options: list[str] | None = None
    extra_components: list[str] | None = None
    capability_ignore_list: list[Capability] | None = None
    value_is_integer: bool = False


CAPABILITIES_TO_SELECT: dict[Capability | str, SmartThingsSelectDescription] = {
    Capability.DISHWASHER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.DISHWASHER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
    ),
    Capability.DRYER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.DRYER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
        default_options=["run", "pause", "stop"],
    ),
    Capability.WASHER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.WASHER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
        default_options=["run", "pause", "stop"],
    ),
    Capability.SAMSUNG_CE_AUTO_DISPENSE_DETERGENT: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_AUTO_DISPENSE_DETERGENT,
        translation_key="detergent_amount",
        options_attribute=Attribute.SUPPORTED_AMOUNT,
        status_attribute=Attribute.AMOUNT,
        command=Command.SET_AMOUNT,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_FLEXIBLE_AUTO_DISPENSE_DETERGENT: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_FLEXIBLE_AUTO_DISPENSE_DETERGENT,
        translation_key="flexible_detergent_amount",
        options_attribute=Attribute.SUPPORTED_AMOUNT,
        status_attribute=Attribute.AMOUNT,
        command=Command.SET_AMOUNT,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_LAMP: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_LAMP,
        translation_key="lamp",
        options_attribute=Attribute.SUPPORTED_BRIGHTNESS_LEVEL,
        status_attribute=Attribute.BRIGHTNESS_LEVEL,
        command=Command.SET_BRIGHTNESS_LEVEL,
        options_map=LAMP_TO_HA,
        entity_category=EntityCategory.CONFIG,
        extra_components=["hood"],
        capability_ignore_list=[Capability.SAMSUNG_CE_CONNECTION_STATE],
    ),
    Capability.CUSTOM_WASHER_SPIN_LEVEL: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_SPIN_LEVEL,
        translation_key="spin_level",
        options_attribute=Attribute.SUPPORTED_WASHER_SPIN_LEVEL,
        status_attribute=Attribute.WASHER_SPIN_LEVEL,
        command=Command.SET_WASHER_SPIN_LEVEL,
        options_map=WASHER_SPIN_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.CUSTOM_WASHER_SOIL_LEVEL: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_SOIL_LEVEL,
        translation_key="soil_level",
        options_attribute=Attribute.SUPPORTED_WASHER_SOIL_LEVEL,
        status_attribute=Attribute.WASHER_SOIL_LEVEL,
        command=Command.SET_WASHER_SOIL_LEVEL,
        options_map=WASHER_SOIL_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.CUSTOM_WASHER_WATER_TEMPERATURE: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_WATER_TEMPERATURE,
        translation_key="water_temperature",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_WASHER_WATER_TEMPERATURE,
        status_attribute=Attribute.WASHER_WATER_TEMPERATURE,
        command=Command.SET_WASHER_WATER_TEMPERATURE,
        options_map=WASHER_WATER_TEMPERATURE_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_DUST_FILTER_ALARM: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DUST_FILTER_ALARM,
        translation_key="dust_filter_alarm",
        options_attribute=Attribute.SUPPORTED_ALARM_THRESHOLDS,
        status_attribute=Attribute.ALARM_THRESHOLD,
        command=Command.SET_ALARM_THRESHOLD,
        entity_category=EntityCategory.CONFIG,
        value_is_integer=True,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add select entities for a config entry."""
    entry_data = entry.runtime_data
    entities: list[SelectEntity] = [
        SmartThingsSelectEntity(entry_data.client, device, description, component)
        for capability, description in CAPABILITIES_TO_SELECT.items()
        for device in entry_data.devices.values()
        for component in device.status
        if capability in device.status[component]
        and (
            component == MAIN
            or (
                description.extra_components is not None
                and component in description.extra_components
            )
        )
        and (
            description.capability_ignore_list is None
            or any(
                capability not in device.status[component]
                for capability in description.capability_ignore_list
            )
        )
    ]
    # Add FSV select entities
    entities.extend(
        SmartThingsFsvSelect(entry_data.client, device, component, description)
        for device in entry_data.devices.values()
        for component in device.status
        if Capability.SAMSUNG_CE_EHS_FSV_SETTINGS in device.status[component]
        for fsv_settings in device.status[component][
            Capability.SAMSUNG_CE_EHS_FSV_SETTINGS
        ].values()
        if fsv_settings.value is not None and isinstance(fsv_settings.value, list)
        for fsv_setting in fsv_settings.value
        if (fsv_id := fsv_setting["id"]) in FSV_SELECT_DESCRIPTIONS
        and (description := FSV_SELECT_DESCRIPTIONS[fsv_id]) is not None
    )
    async_add_entities(entities)


class SmartThingsSelectEntity(SmartThingsEntity, SelectEntity):
    """Define a SmartThings select."""

    entity_description: SmartThingsSelectDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSelectDescription,
        component: str,
    ) -> None:
        """Initialize the instance."""
        capabilities = {entity_description.key}
        if entity_description.requires_remote_control_status:
            capabilities.add(Capability.REMOTE_CONTROL_STATUS)
        super().__init__(client, device, capabilities, component=component)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.device.device_id}_{component}_{entity_description.key}_{entity_description.status_attribute}_{entity_description.status_attribute}"

    @property
    def options(self) -> list[str]:
        """Return the list of options."""
        options: list[str] = (
            self.get_attribute_value(
                self.entity_description.key, self.entity_description.options_attribute
            )
            or self.entity_description.default_options
            or []
        )
        if self.entity_description.options_map:
            options = [
                self.entity_description.options_map.get(option, option)
                for option in options
            ]
        if self.entity_description.value_is_integer:
            options = [str(option) for option in options]
        return options

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        option = self.get_attribute_value(
            self.entity_description.key, self.entity_description.status_attribute
        )
        if self.entity_description.options_map:
            option = self.entity_description.options_map.get(option)
        if self.entity_description.value_is_integer and option is not None:
            option = str(option)
        return option

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if (
            self.entity_description.requires_remote_control_status
            and self.get_attribute_value(
                Capability.REMOTE_CONTROL_STATUS, Attribute.REMOTE_CONTROL_ENABLED
            )
            == "false"
        ):
            raise ServiceValidationError(
                "Can only be updated when remote control is enabled"
            )
        new_option: str | int = option
        if self.entity_description.options_map:
            new_option = next(
                (
                    key
                    for key, value in self.entity_description.options_map.items()
                    if value == option
                ),
                new_option,
            )
        if self.entity_description.value_is_integer:
            new_option = int(option)
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
            new_option,
        )


@dataclass(frozen=True, kw_only=True)
class SmartThingsFsvSelectEntityDescription(SelectEntityDescription):
    """Describe a SmartThings FSV setting select entity."""

    fsv_id: str
    num_options: int
    options_offset: int = 0


# FSV select entity descriptions for enum-like settings
FSV_SELECT_DESCRIPTIONS: dict[str, SmartThingsFsvSelectEntityDescription] = {
    "2041": SmartThingsFsvSelectEntityDescription(
        key="2041",
        fsv_id="2041",
        translation_key="water_law_type_heating",
        num_options=2,
        options_offset=1,
        entity_category=EntityCategory.CONFIG,
    ),
    "2081": SmartThingsFsvSelectEntityDescription(
        key="2081",
        fsv_id="2081",
        translation_key="water_law_type_cooling",
        num_options=2,
        options_offset=1,
        entity_category=EntityCategory.CONFIG,
    ),
    "2091": SmartThingsFsvSelectEntityDescription(
        key="2091",
        fsv_id="2091",
        translation_key="external_run_input_zone_1",
        num_options=5,
        entity_category=EntityCategory.CONFIG,
    ),
    "2092": SmartThingsFsvSelectEntityDescription(
        key="2092",
        fsv_id="2092",
        translation_key="external_run_input_zone_2",
        num_options=5,
        entity_category=EntityCategory.CONFIG,
    ),
    "2093": SmartThingsFsvSelectEntityDescription(
        key="2093",
        fsv_id="2093",
        translation_key="remote_controller_room_temp_control",
        num_options=4,
        options_offset=1,
        entity_category=EntityCategory.CONFIG,
    ),
    "3011": SmartThingsFsvSelectEntityDescription(
        key="3011",
        fsv_id="3011",
        translation_key="dhw_tank_function",
        num_options=3,
        entity_category=EntityCategory.CONFIG,
    ),
    "3042": SmartThingsFsvSelectEntityDescription(
        key="3042",
        fsv_id="3042",
        translation_key="disinfection_interval_day",
        num_options=8,
        entity_category=EntityCategory.CONFIG,
    ),
    "3061": SmartThingsFsvSelectEntityDescription(
        key="3061",
        fsv_id="3061",
        translation_key="use_dhw_thermostat",
        num_options=3,
        entity_category=EntityCategory.CONFIG,
    ),
    "3071": SmartThingsFsvSelectEntityDescription(
        key="3071",
        fsv_id="3071",
        translation_key="three_way_valve_direction",
        num_options=2,
        entity_category=EntityCategory.CONFIG,
    ),
    "4011": SmartThingsFsvSelectEntityDescription(
        key="4011",
        fsv_id="4011",
        translation_key="dhw_space_heating_priority",
        num_options=2,
        entity_category=EntityCategory.CONFIG,
    ),
    "4021": SmartThingsFsvSelectEntityDescription(
        key="4021",
        fsv_id="4021",
        translation_key="backup_heater_application",
        num_options=3,
        entity_category=EntityCategory.CONFIG,
    ),
    "4022": SmartThingsFsvSelectEntityDescription(
        key="4022",
        fsv_id="4022",
        translation_key="buh_bsh_priority",
        num_options=3,
        entity_category=EntityCategory.CONFIG,
    ),
    "4041": SmartThingsFsvSelectEntityDescription(
        key="4041",
        fsv_id="4041",
        translation_key="mixing_valve_application",
        num_options=3,
        entity_category=EntityCategory.CONFIG,
    ),
    "4051": SmartThingsFsvSelectEntityDescription(
        key="4051",
        fsv_id="4051",
        translation_key="inverter_pump_application",
        num_options=3,
        entity_category=EntityCategory.CONFIG,
    ),
    "4061": SmartThingsFsvSelectEntityDescription(
        key="4061",
        fsv_id="4061",
        translation_key="two_zone_control",
        num_options=2,
        entity_category=EntityCategory.CONFIG,
    ),
    "5022": SmartThingsFsvSelectEntityDescription(
        key="5022",
        fsv_id="5022",
        translation_key="dhw_saving_mode",
        num_options=2,
        entity_category=EntityCategory.CONFIG,
    ),
    "5033": SmartThingsFsvSelectEntityDescription(
        key="5033",
        fsv_id="5033",
        translation_key="tdm_priority",
        num_options=2,
        entity_category=EntityCategory.CONFIG,
    ),
    "5042": SmartThingsFsvSelectEntityDescription(
        key="5042",
        fsv_id="5042",
        translation_key="power_peak_control_forced_off_parts",
        num_options=4,
        entity_category=EntityCategory.CONFIG,
    ),
    "5061": SmartThingsFsvSelectEntityDescription(
        key="5061",
        fsv_id="5061",
        translation_key="ch_dhw_supply_ratio",
        num_options=7,
        options_offset=1,
        entity_category=EntityCategory.CONFIG,
    ),
    "5094": SmartThingsFsvSelectEntityDescription(
        key="5094",
        fsv_id="5094",
        translation_key="smart_grid_dhw_mode",
        num_options=2,
        entity_category=EntityCategory.CONFIG,
    ),
}


class SmartThingsFsvSelect(SmartThingsFsvEntity, SelectEntity):
    """Define a SmartThings FSV select."""

    entity_description: SmartThingsFsvSelectEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        component: str,
        description: SmartThingsFsvSelectEntityDescription,
    ) -> None:
        """Initialize the FSV select."""
        super().__init__(
            client,
            device,
            component=component,
            fsv_id=description.fsv_id,
        )
        self.entity_description = description
        self._attr_options = [
            str(i + description.options_offset) for i in range(description.num_options)
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = self._get_fsv_value()
        if value is None:
            return None
        return str(value)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self._async_set_fsv_value(int(option))
