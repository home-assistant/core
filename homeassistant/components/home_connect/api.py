"""API for Home Connect bound to HASS OAuth."""

from asyncio import run_coroutine_threadsafe
import logging
from typing import Any

import homeconnect
from homeconnect.api import HomeConnectError

from homeassistant import config_entries, core
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    CONF_DEVICE,
    CONF_ENTITIES,
    PERCENTAGE,
    TIME_SECONDS,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    ATTR_AMBIENT,
    ATTR_DESC,
    ATTR_DEVICE,
    ATTR_KEY,
    ATTR_SENSOR_TYPE,
    ATTR_SETTING,
    ATTR_SIGN,
    ATTR_UNIT,
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    BSH_CHILD_LOCK,
    BSH_OPERATION_STATE,
    BSH_POWER_OFF,
    BSH_POWER_STANDBY,
    FREEZER_SETPOINT_TEMPERATURE,
    FREEZER_SUPER_MODE,
    FRIDGE_FRESH_MODE,
    FRIDGE_SETPOINT_TEMPERATURE,
    FRIDGE_SUPER_MODE,
    FRIDGE_VACATION_MODE,
    REFRIGERATION_ECO_MODE,
    SIGNAL_UPDATE_ENTITIES,
)

_LOGGER = logging.getLogger(__name__)


class ConfigEntryAuth(homeconnect.HomeConnectAPI):
    """Provide Home Connect authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ) -> None:
        """Initialize Home Connect Auth."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        super().__init__(self.session.token)
        self.devices: list[dict[str, Any]] = []

    def refresh_tokens(self) -> dict:
        """Refresh and return new Home Connect tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token

    def get_devices(self):
        """Get a dictionary of devices."""
        appl = self.get_appliances()
        devices = []
        for app in appl:
            if app.type == "Dryer":
                device = Dryer(self.hass, app)
            elif app.type == "Washer":
                device = Washer(self.hass, app)
            elif app.type == "Dishwasher":
                device = Dishwasher(self.hass, app)
            elif app.type == "FridgeFreezer":
                device = FridgeFreezer(self.hass, app)
            elif app.type == "Refrigerator":
                device = Refrigerator(self.hass, app)
            elif app.type == "Freezer":
                device = Freezer(self.hass, app)
            elif app.type == "Oven":
                device = Oven(self.hass, app)
            elif app.type == "CoffeeMaker":
                device = CoffeeMaker(self.hass, app)
            elif app.type == "Hood":
                device = Hood(self.hass, app)
            elif app.type == "Hob":
                device = Hob(self.hass, app)
            elif app.type == "CookProcessor":
                device = CookProcessor(self.hass, app)
            else:
                _LOGGER.warning("Appliance type %s not implemented", app.type)
                continue
            devices.append(
                {CONF_DEVICE: device, CONF_ENTITIES: device.get_entity_info()}
            )
        self.devices = devices
        return devices


class HomeConnectDevice:
    """Generic Home Connect device."""

    # for some devices, this is instead BSH_POWER_STANDBY
    # see https://developer.home-connect.com/docs/settings/power_state
    power_off_state = BSH_POWER_OFF

    def __init__(self, hass, appliance):
        """Initialize the device class."""
        self.hass = hass
        self.appliance = appliance

    def initialize(self):
        """Fetch the info needed to initialize the device."""
        try:
            self.appliance.get_status()
        except (HomeConnectError, ValueError):
            _LOGGER.debug("Unable to fetch appliance status. Probably offline")
        try:
            self.appliance.get_settings()
        except (HomeConnectError, ValueError):
            _LOGGER.debug("Unable to fetch settings. Probably offline")
        try:
            program_active = self.appliance.get_programs_active()
        except (HomeConnectError, ValueError):
            _LOGGER.debug("Unable to fetch active programs. Probably offline")
            program_active = None
        if program_active and ATTR_KEY in program_active:
            self.appliance.status[BSH_ACTIVE_PROGRAM] = {
                ATTR_VALUE: program_active[ATTR_KEY]
            }
        self.appliance.listen_events(callback=self.event_callback)

    def event_callback(self, appliance):
        """Handle event."""
        _LOGGER.debug("Update triggered on %s", appliance.name)
        _LOGGER.debug(self.appliance.status)
        dispatcher_send(self.hass, SIGNAL_UPDATE_ENTITIES, appliance.haId)


class DeviceWithPrograms(HomeConnectDevice):
    """Device with programs."""

    PROGRAMS: list[dict[str, str]] = []

    def get_programs_available(self):
        """Get the available programs."""
        return self.PROGRAMS

    def get_program_switches(self):
        """Get a dictionary with info about program switches.

        There will be one switch for each program.
        """
        programs = self.get_programs_available()
        return [{ATTR_DEVICE: self, "program_name": p["name"]} for p in programs]

    def get_program_sensors(self):
        """Get a dictionary with info about program sensors.

        There will be one of the four types of sensors for each
        device.
        """
        sensors = {
            "Remaining Program Time": (None, None, SensorDeviceClass.TIMESTAMP, 1),
            "Duration": (TIME_SECONDS, "mdi:update", None, 1),
            "Program Progress": (PERCENTAGE, "mdi:progress-clock", None, 1),
        }
        return [
            {
                ATTR_DEVICE: self,
                ATTR_DESC: k,
                ATTR_UNIT: unit,
                ATTR_KEY: "BSH.Common.Option.{}".format(k.replace(" ", "")),
                ATTR_ICON: icon,
                ATTR_DEVICE_CLASS: device_class,
                ATTR_SIGN: sign,
            }
            for k, (unit, icon, device_class, sign) in sensors.items()
        ]


class DeviceWithOpState(HomeConnectDevice):
    """Device that has an operation state sensor."""

    def get_opstate_sensor(self):
        """Get a list with info about operation state sensors."""

        return [
            {
                ATTR_DEVICE: self,
                ATTR_DESC: "Operation State",
                ATTR_UNIT: None,
                ATTR_KEY: BSH_OPERATION_STATE,
                ATTR_ICON: "mdi:state-machine",
                ATTR_DEVICE_CLASS: None,
                ATTR_SIGN: 1,
            }
        ]


class DeviceWithDoor(HomeConnectDevice):
    """Device that has a door sensor."""

    def get_door_entity(self):
        """Get a dictionary with info about the door binary sensor."""
        return {
            ATTR_DEVICE: self,
            ATTR_DESC: "Door",
            ATTR_SENSOR_TYPE: "door",
            ATTR_DEVICE_CLASS: "door",
        }


class DeviceWithLight(HomeConnectDevice):
    """Device that has lighting."""

    def get_light_entity(self):
        """Get a dictionary with info about the lighting."""
        return {ATTR_DEVICE: self, ATTR_DESC: "Light", ATTR_AMBIENT: None}


class DeviceWithAmbientLight(HomeConnectDevice):
    """Device that has ambient lighting."""

    def get_ambientlight_entity(self):
        """Get a dictionary with info about the ambient lighting."""
        return {ATTR_DEVICE: self, ATTR_DESC: "AmbientLight", ATTR_AMBIENT: True}


class DeviceWithRemoteControl(HomeConnectDevice):
    """Device that has Remote Control binary sensor."""

    def get_remote_control(self):
        """Get a dictionary with info about the remote control sensor."""
        return {
            ATTR_DEVICE: self,
            ATTR_DESC: "Remote Control",
            ATTR_SENSOR_TYPE: "remote_control",
        }


class DeviceWithRemoteStart(HomeConnectDevice):
    """Device that has a Remote Start binary sensor."""

    def get_remote_start(self):
        """Get a dictionary with info about the remote start sensor."""
        return {
            ATTR_DEVICE: self,
            ATTR_DESC: "Remote Start",
            ATTR_SENSOR_TYPE: "remote_start",
        }


class DeviceWithSettings(HomeConnectDevice):
    """Device with settings."""

    SETTINGS: dict[str, dict[str, str]] = {}

    def get_settings_available(self):
        """Get the available settings."""
        available_settings = {}
        settings = self.appliance.get_settings()

        for setting_name, setting in self.SETTINGS.items():
            if setting_name in settings:
                available_settings[setting_name] = setting

        return available_settings

    def get_setting_switches(self):
        """Get a dictionary with info about setting switches."""
        switches = []
        settings = self.get_settings_available()
        for setting_name, setting in settings.items():
            if setting.get(ATTR_SENSOR_TYPE) == "switch":
                switches += [
                    {
                        ATTR_DEVICE: self,
                        ATTR_SETTING: setting_name,
                        ATTR_DESC: setting.get(ATTR_DESC),
                        ATTR_ICON: setting.get(ATTR_ICON),
                    }
                ]

        return switches

    def get_setting_number_entities(self):
        """Get a dictionary with info about setting number entities."""
        number_entities = []
        settings = self.get_settings_available()
        for setting_name, setting in settings.items():
            if setting.get(ATTR_SENSOR_TYPE) == "number":
                number_entities += [
                    {
                        ATTR_DEVICE: self,
                        ATTR_SETTING: setting_name,
                        ATTR_DESC: setting.get(ATTR_DESC),
                        ATTR_ICON: setting.get(ATTR_ICON),
                    }
                ]

        return number_entities


class Dryer(
    DeviceWithDoor,
    DeviceWithOpState,
    DeviceWithPrograms,
    DeviceWithRemoteControl,
    DeviceWithRemoteStart,
    DeviceWithSettings,
):
    """Dryer class."""

    SETTINGS = {
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
    }

    PROGRAMS = [
        {"name": "LaundryCare.Dryer.Program.Cotton"},
        {"name": "LaundryCare.Dryer.Program.Synthetic"},
        {"name": "LaundryCare.Dryer.Program.Mix"},
        {"name": "LaundryCare.Dryer.Program.Blankets"},
        {"name": "LaundryCare.Dryer.Program.BusinessShirts"},
        {"name": "LaundryCare.Dryer.Program.DownFeathers"},
        {"name": "LaundryCare.Dryer.Program.Hygiene"},
        {"name": "LaundryCare.Dryer.Program.Jeans"},
        {"name": "LaundryCare.Dryer.Program.Outdoor"},
        {"name": "LaundryCare.Dryer.Program.SyntheticRefresh"},
        {"name": "LaundryCare.Dryer.Program.Towels"},
        {"name": "LaundryCare.Dryer.Program.Delicates"},
        {"name": "LaundryCare.Dryer.Program.Super40"},
        {"name": "LaundryCare.Dryer.Program.Shirts15"},
        {"name": "LaundryCare.Dryer.Program.Pillow"},
        {"name": "LaundryCare.Dryer.Program.AntiShrink"},
        {"name": "LaundryCare.Dryer.Program.TimeCold"},
        {"name": "LaundryCare.Dryer.Program.TimeWarm"},
    ]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()
        remote_control = self.get_remote_control()
        remote_start = self.get_remote_start()
        op_state_sensor = self.get_opstate_sensor()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity, remote_control, remote_start],
            "switch": program_switches,
            "sensor": program_sensors + op_state_sensor,
        }


class Dishwasher(
    DeviceWithDoor,
    DeviceWithAmbientLight,
    DeviceWithOpState,
    DeviceWithPrograms,
    DeviceWithRemoteControl,
    DeviceWithRemoteStart,
    DeviceWithSettings,
):
    """Dishwasher class."""

    SETTINGS = {
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
    }

    PROGRAMS = [
        {"name": "Dishcare.Dishwasher.Program.Auto1"},
        {"name": "Dishcare.Dishwasher.Program.Auto2"},
        {"name": "Dishcare.Dishwasher.Program.Auto3"},
        {"name": "Dishcare.Dishwasher.Program.Eco50"},
        {"name": "Dishcare.Dishwasher.Program.Quick45"},
        {"name": "Dishcare.Dishwasher.Program.Intensiv70"},
        {"name": "Dishcare.Dishwasher.Program.Normal65"},
        {"name": "Dishcare.Dishwasher.Program.Glas40"},
        {"name": "Dishcare.Dishwasher.Program.GlassCare"},
        {"name": "Dishcare.Dishwasher.Program.PreRinse"},
        {"name": "Dishcare.Dishwasher.Program.NightWash"},
        {"name": "Dishcare.Dishwasher.Program.Quick65"},
        {"name": "Dishcare.Dishwasher.Program.Normal45"},
        {"name": "Dishcare.Dishwasher.Program.Intensiv45"},
        {"name": "Dishcare.Dishwasher.Program.AutoHalfLoad"},
        {"name": "Dishcare.Dishwasher.Program.IntensivPower"},
        {"name": "Dishcare.Dishwasher.Program.MagicDaily"},
        {"name": "Dishcare.Dishwasher.Program.Super60"},
        {"name": "Dishcare.Dishwasher.Program.Kurz60"},
        {"name": "Dishcare.Dishwasher.Program.ExpressSparkle65"},
        {"name": "Dishcare.Dishwasher.Program.MachineCare"},
        {"name": "Dishcare.Dishwasher.Program.SteamFresh"},
        {"name": "Dishcare.Dishwasher.Program.MaximumCleaning"},
    ]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()
        remote_control = self.get_remote_control()
        remote_start = self.get_remote_start()
        op_state_sensor = self.get_opstate_sensor()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity, remote_control, remote_start],
            "switch": program_switches,
            "sensor": program_sensors + op_state_sensor,
        }


class Oven(
    DeviceWithDoor,
    DeviceWithOpState,
    DeviceWithPrograms,
    DeviceWithRemoteControl,
    DeviceWithRemoteStart,
    DeviceWithSettings,
):
    """Oven class."""

    SETTINGS = {
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
    }

    PROGRAMS = [
        {"name": "Cooking.Oven.Program.HeatingMode.PreHeating"},
        {"name": "Cooking.Oven.Program.HeatingMode.HotAir"},
        {"name": "Cooking.Oven.Program.HeatingMode.TopBottomHeating"},
        {"name": "Cooking.Oven.Program.HeatingMode.PizzaSetting"},
        {"name": "Cooking.Oven.Program.Microwave.600Watt"},
    ]

    power_off_state = BSH_POWER_STANDBY

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()
        remote_control = self.get_remote_control()
        remote_start = self.get_remote_start()
        op_state_sensor = self.get_opstate_sensor()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity, remote_control, remote_start],
            "switch": program_switches,
            "sensor": program_sensors + op_state_sensor,
        }


class Washer(
    DeviceWithDoor,
    DeviceWithOpState,
    DeviceWithPrograms,
    DeviceWithRemoteControl,
    DeviceWithRemoteStart,
    DeviceWithSettings,
):
    """Washer class."""

    SETTINGS = {
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
    }

    PROGRAMS = [
        {"name": "LaundryCare.Washer.Program.Cotton"},
        {"name": "LaundryCare.Washer.Program.Cotton.CottonEco"},
        {"name": "LaundryCare.Washer.Program.EasyCare"},
        {"name": "LaundryCare.Washer.Program.Mix"},
        {"name": "LaundryCare.Washer.Program.DelicatesSilk"},
        {"name": "LaundryCare.Washer.Program.Wool"},
        {"name": "LaundryCare.Washer.Program.Sensitive"},
        {"name": "LaundryCare.Washer.Program.Auto30"},
        {"name": "LaundryCare.Washer.Program.Auto40"},
        {"name": "LaundryCare.Washer.Program.Auto60"},
        {"name": "LaundryCare.Washer.Program.Chiffon"},
        {"name": "LaundryCare.Washer.Program.Curtains"},
        {"name": "LaundryCare.Washer.Program.DarkWash"},
        {"name": "LaundryCare.Washer.Program.Dessous"},
        {"name": "LaundryCare.Washer.Program.Monsoon"},
        {"name": "LaundryCare.Washer.Program.Outdoor"},
        {"name": "LaundryCare.Washer.Program.PlushToy"},
        {"name": "LaundryCare.Washer.Program.ShirtsBlouses"},
        {"name": "LaundryCare.Washer.Program.SportFitness"},
        {"name": "LaundryCare.Washer.Program.Towels"},
        {"name": "LaundryCare.Washer.Program.WaterProof"},
    ]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()
        remote_control = self.get_remote_control()
        remote_start = self.get_remote_start()
        op_state_sensor = self.get_opstate_sensor()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity, remote_control, remote_start],
            "switch": program_switches,
            "sensor": program_sensors + op_state_sensor,
        }


class CoffeeMaker(
    DeviceWithOpState, DeviceWithPrograms, DeviceWithRemoteStart, DeviceWithSettings
):
    """Coffee maker class."""

    SETTINGS = {
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
    }

    PROGRAMS = [
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoMacchiato"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.Coffee"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.Cappuccino"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.LatteMacchiato"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeLatte"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Americano"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoDoppio"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.FlatWhite"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Galao"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.MilkFroth"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.WarmMilk"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.Beverage.Ristretto"},
        {"name": "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Cortado"},
    ]

    power_off_state = BSH_POWER_STANDBY

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        remote_start = self.get_remote_start()
        op_state_sensor = self.get_opstate_sensor()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [remote_start],
            "switch": program_switches,
            "sensor": program_sensors + op_state_sensor,
        }


class Hood(
    DeviceWithLight,
    DeviceWithAmbientLight,
    DeviceWithOpState,
    DeviceWithPrograms,
    DeviceWithRemoteControl,
    DeviceWithRemoteStart,
):
    """Hood class."""

    PROGRAMS = [
        {"name": "Cooking.Common.Program.Hood.Automatic"},
        {"name": "Cooking.Common.Program.Hood.Venting"},
        {"name": "Cooking.Common.Program.Hood.DelayedShutOff"},
    ]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        remote_control = self.get_remote_control()
        remote_start = self.get_remote_start()
        light_entity = self.get_light_entity()
        ambientlight_entity = self.get_ambientlight_entity()
        op_state_sensor = self.get_opstate_sensor()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [remote_control, remote_start],
            "switch": program_switches,
            "sensor": program_sensors + op_state_sensor,
            "light": [light_entity, ambientlight_entity],
        }


class FridgeFreezer(DeviceWithDoor, DeviceWithSettings):
    """Fridge/Freezer class."""

    SETTINGS = {
        FRIDGE_VACATION_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Vacation Mode",
            ATTR_ICON: "mdi:bag-suitcase",
        },
        FRIDGE_SUPER_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Fridge Super Mode",
            ATTR_ICON: "mdi:snowflake",
        },
        FREEZER_SUPER_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Freezer Super Mode",
            ATTR_ICON: "mdi:snowflake",
        },
        REFRIGERATION_ECO_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Eco Mode",
        },
        FRIDGE_FRESH_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Fresh Mode",
        },
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
        FRIDGE_SETPOINT_TEMPERATURE: {
            ATTR_SENSOR_TYPE: "number",
            ATTR_DESC: "Fridge Setpoint",
            ATTR_ICON: "mdi:thermometer",
        },
        FREEZER_SETPOINT_TEMPERATURE: {
            ATTR_SENSOR_TYPE: "number",
            ATTR_DESC: "Freezer Setpoint",
            ATTR_ICON: "mdi:thermometer",
        },
    }

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()

        setting_switches = self.get_setting_switches()
        setting_number_entities = self.get_setting_number_entities()

        return {
            "binary_sensor": [door_entity],
            "switch": setting_switches,
            "number": setting_number_entities,
        }


class Refrigerator(DeviceWithDoor, DeviceWithSettings):
    """Refrigerator class."""

    SETTINGS = {
        FRIDGE_VACATION_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Vacation Mode",
            ATTR_ICON: "mdi:bag-suitcase",
        },
        FRIDGE_SUPER_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Super Mode",
            ATTR_ICON: "mdi:snowflake",
        },
        REFRIGERATION_ECO_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Eco Mode",
        },
        FRIDGE_FRESH_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Fresh Mode",
        },
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
        FRIDGE_SETPOINT_TEMPERATURE: {
            ATTR_SENSOR_TYPE: "number",
            ATTR_DESC: "Setpoint",
            ATTR_ICON: "mdi:thermometer",
        },
    }

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()

        setting_switches = self.get_setting_switches()
        setting_number_entities = self.get_setting_number_entities()

        return {
            "binary_sensor": [door_entity],
            "switch": setting_switches,
            "number": setting_number_entities,
        }


class Freezer(DeviceWithDoor, DeviceWithSettings):
    """Freezer class."""

    SETTINGS = {
        FREEZER_SUPER_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Super Mode",
            ATTR_ICON: "mdi:snowflake",
        },
        REFRIGERATION_ECO_MODE: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Eco Mode",
        },
        BSH_CHILD_LOCK: {
            ATTR_SENSOR_TYPE: "switch",
            ATTR_DESC: "Child Lock",
            ATTR_ICON: "mdi:lock",
        },
        FREEZER_SETPOINT_TEMPERATURE: {
            ATTR_SENSOR_TYPE: "number",
            ATTR_DESC: "Setpoint",
            ATTR_ICON: "mdi:thermometer",
        },
    }

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()

        setting_switches = self.get_setting_switches()
        setting_number_entities = self.get_setting_number_entities()

        return {
            "binary_sensor": [door_entity],
            "switch": setting_switches,
            "number": setting_number_entities,
        }


class Hob(DeviceWithOpState, DeviceWithPrograms, DeviceWithRemoteControl):
    """Hob class."""

    PROGRAMS = [{"name": "Cooking.Hob.Program.PowerLevelMode"}]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        remote_control = self.get_remote_control()
        op_state_sensor = self.get_opstate_sensor()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [remote_control],
            "switch": program_switches,
            "sensor": program_sensors + op_state_sensor,
        }


class CookProcessor(DeviceWithOpState):
    """CookProcessor class."""

    power_off_state = BSH_POWER_STANDBY

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        op_state_sensor = self.get_opstate_sensor()
        return {"sensor": op_state_sensor}
