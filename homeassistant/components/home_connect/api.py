"""API for Home Connect bound to HASS OAuth."""

from asyncio import run_coroutine_threadsafe
import logging

import homeconnect
from homeconnect.api import HomeConnectError

from homeassistant import config_entries, core
from homeassistant.const import DEVICE_CLASS_TIMESTAMP, PERCENTAGE, TIME_SECONDS
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    BSH_ACTIVE_PROGRAM,
    BSH_POWER_OFF,
    BSH_POWER_STANDBY,
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
    ):
        """Initialize Home Connect Auth."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        super().__init__(self.session.token)
        self.devices = []

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
            elif app.type == "Oven":
                device = Oven(self.hass, app)
            elif app.type == "CoffeeMaker":
                device = CoffeeMaker(self.hass, app)
            elif app.type == "Hood":
                device = Hood(self.hass, app)
            elif app.type == "Hob":
                device = Hob(self.hass, app)
            else:
                _LOGGER.warning("Appliance type %s not implemented", app.type)
                continue
            devices.append({"device": device, "entities": device.get_entity_info()})
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
        if program_active and "key" in program_active:
            self.appliance.status[BSH_ACTIVE_PROGRAM] = {"value": program_active["key"]}
        self.appliance.listen_events(callback=self.event_callback)

    def event_callback(self, appliance):
        """Handle event."""
        _LOGGER.debug("Update triggered on %s", appliance.name)
        _LOGGER.debug(self.appliance.status)
        dispatcher_send(self.hass, SIGNAL_UPDATE_ENTITIES, appliance.haId)


class DeviceWithPrograms(HomeConnectDevice):
    """Device with programs."""

    PROGRAMS = []

    def get_programs_available(self):
        """Get the available programs."""
        return self.PROGRAMS

    def get_program_switches(self):
        """Get a dictionary with info about program switches.

        There will be one switch for each program.
        """
        programs = self.get_programs_available()
        return [{"device": self, "program_name": p["name"]} for p in programs]

    def get_program_sensors(self):
        """Get a dictionary with info about program sensors.

        There will be one of the four types of sensors for each
        device.
        """
        sensors = {
            "Remaining Program Time": (None, None, DEVICE_CLASS_TIMESTAMP, 1),
            "Duration": (TIME_SECONDS, "mdi:update", None, 1),
            "Program Progress": (PERCENTAGE, "mdi:progress-clock", None, 1),
        }
        return [
            {
                "device": self,
                "desc": k,
                "unit": unit,
                "key": "BSH.Common.Option.{}".format(k.replace(" ", "")),
                "icon": icon,
                "device_class": device_class,
                "sign": sign,
            }
            for k, (unit, icon, device_class, sign) in sensors.items()
        ]


class DeviceWithDoor(HomeConnectDevice):
    """Device that has a door sensor."""

    def get_door_entity(self):
        """Get a dictionary with info about the door binary sensor."""
        return {
            "device": self,
            "desc": "Door",
            "device_class": "door",
        }


class DeviceWithLight(HomeConnectDevice):
    """Device that has lighting."""

    def get_light_entity(self):
        """Get a dictionary with info about the lighting."""
        return {
            "device": self,
            "desc": "Light",
            "ambient": None,
        }


class DeviceWithAmbientLight(HomeConnectDevice):
    """Device that has ambient lighting."""

    def get_ambientlight_entity(self):
        """Get a dictionary with info about the ambient lighting."""
        return {
            "device": self,
            "desc": "AmbientLight",
            "ambient": True,
        }


class Dryer(DeviceWithDoor, DeviceWithPrograms):
    """Dryer class."""

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
    ]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity],
            "switch": program_switches,
            "sensor": program_sensors,
        }


class Dishwasher(DeviceWithDoor, DeviceWithAmbientLight, DeviceWithPrograms):
    """Dishwasher class."""

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
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity],
            "switch": program_switches,
            "sensor": program_sensors,
        }


class Oven(DeviceWithDoor, DeviceWithPrograms):
    """Oven class."""

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
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity],
            "switch": program_switches,
            "sensor": program_sensors,
        }


class Washer(DeviceWithDoor, DeviceWithPrograms):
    """Washer class."""

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
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "binary_sensor": [door_entity],
            "switch": program_switches,
            "sensor": program_sensors,
        }


class CoffeeMaker(DeviceWithPrograms):
    """Coffee maker class."""

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
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {"switch": program_switches, "sensor": program_sensors}


class Hood(DeviceWithLight, DeviceWithAmbientLight, DeviceWithPrograms):
    """Hood class."""

    PROGRAMS = [
        {"name": "Cooking.Common.Program.Hood.Automatic"},
        {"name": "Cooking.Common.Program.Hood.Venting"},
        {"name": "Cooking.Common.Program.Hood.DelayedShutOff"},
    ]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        light_entity = self.get_light_entity()
        ambientlight_entity = self.get_ambientlight_entity()
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {
            "switch": program_switches,
            "sensor": program_sensors,
            "light": [light_entity, ambientlight_entity],
        }


class FridgeFreezer(DeviceWithDoor):
    """Fridge/Freezer class."""

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        door_entity = self.get_door_entity()
        return {"binary_sensor": [door_entity]}


class Hob(DeviceWithPrograms):
    """Hob class."""

    PROGRAMS = [{"name": "Cooking.Hob.Program.PowerLevelMode"}]

    def get_entity_info(self):
        """Get a dictionary with infos about the associated entities."""
        program_sensors = self.get_program_sensors()
        program_switches = self.get_program_switches()
        return {"switch": program_switches, "sensor": program_sensors}
