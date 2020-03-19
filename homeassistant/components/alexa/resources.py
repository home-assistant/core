"""Alexa Resources and Assets."""


class AlexaGlobalCatalog:
    """The Global Alexa catalog.

    https://developer.amazon.com/docs/device-apis/resources-and-assets.html#global-alexa-catalog

    You can use the global Alexa catalog for pre-defined names of devices, settings, values, and units.
    This catalog is localized into all the languages that Alexa supports.

    You can reference the following catalog of pre-defined friendly names.
    Each item in the following list is an asset identifier followed by its supported friendly names.
    The first friendly name for each identifier is the one displayed in the Alexa mobile app.
    """

    # Air Purifier, Air Cleaner,Clean Air Machine
    DEVICE_NAME_AIR_PURIFIER = "Alexa.DeviceName.AirPurifier"

    # Fan, Blower
    DEVICE_NAME_FAN = "Alexa.DeviceName.Fan"

    # Router, Internet Router, Network Router, Wifi Router, Net Router
    DEVICE_NAME_ROUTER = "Alexa.DeviceName.Router"

    # Shade, Blind, Curtain, Roller, Shutter, Drape, Awning, Window shade, Interior blind
    DEVICE_NAME_SHADE = "Alexa.DeviceName.Shade"

    # Shower
    DEVICE_NAME_SHOWER = "Alexa.DeviceName.Shower"

    # Space Heater, Portable Heater
    DEVICE_NAME_SPACE_HEATER = "Alexa.DeviceName.SpaceHeater"

    # Washer, Washing Machine
    DEVICE_NAME_WASHER = "Alexa.DeviceName.Washer"

    # 2.4G Guest Wi-Fi, 2.4G Guest Network, Guest Network 2.4G, 2G Guest Wifi
    SETTING_2G_GUEST_WIFI = "Alexa.Setting.2GGuestWiFi"

    # 5G Guest Wi-Fi, 5G Guest Network, Guest Network 5G, 5G Guest Wifi
    SETTING_5G_GUEST_WIFI = "Alexa.Setting.5GGuestWiFi"

    # Auto, Automatic, Automatic Mode, Auto Mode
    SETTING_AUTO = "Alexa.Setting.Auto"

    # Direction
    SETTING_DIRECTION = "Alexa.Setting.Direction"

    # Dry Cycle, Dry Preset, Dry Setting, Dryer Cycle, Dryer Preset, Dryer Setting
    SETTING_DRY_CYCLE = "Alexa.Setting.DryCycle"

    # Fan Speed, Airflow speed, Wind Speed, Air speed, Air velocity
    SETTING_FAN_SPEED = "Alexa.Setting.FanSpeed"

    # Guest Wi-fi, Guest Network, Guest Net
    SETTING_GUEST_WIFI = "Alexa.Setting.GuestWiFi"

    # Heat
    SETTING_HEAT = "Alexa.Setting.Heat"

    # Mode
    SETTING_MODE = "Alexa.Setting.Mode"

    # Night, Night Mode
    SETTING_NIGHT = "Alexa.Setting.Night"

    # Opening, Height, Lift, Width
    SETTING_OPENING = "Alexa.Setting.Opening"

    # Oscillate, Swivel, Oscillation, Spin, Back and forth
    SETTING_OSCILLATE = "Alexa.Setting.Oscillate"

    # Preset, Setting
    SETTING_PRESET = "Alexa.Setting.Preset"

    # Quiet, Quiet Mode, Noiseless, Silent
    SETTING_QUIET = "Alexa.Setting.Quiet"

    # Temperature, Temp
    SETTING_TEMPERATURE = "Alexa.Setting.Temperature"

    # Wash Cycle, Wash Preset, Wash setting
    SETTING_WASH_CYCLE = "Alexa.Setting.WashCycle"

    # Water Temperature, Water Temp, Water Heat
    SETTING_WATER_TEMPERATURE = "Alexa.Setting.WaterTemperature"

    # Handheld Shower, Shower Wand, Hand Shower
    SHOWER_HAND_HELD = "Alexa.Shower.HandHeld"

    # Rain Head, Overhead shower, Rain Shower, Rain Spout, Rain Faucet
    SHOWER_RAIN_HEAD = "Alexa.Shower.RainHead"

    # Degrees, Degree
    UNIT_ANGLE_DEGREES = "Alexa.Unit.Angle.Degrees"

    # Radians, Radian
    UNIT_ANGLE_RADIANS = "Alexa.Unit.Angle.Radians"

    # Feet, Foot
    UNIT_DISTANCE_FEET = "Alexa.Unit.Distance.Feet"

    # Inches, Inch
    UNIT_DISTANCE_INCHES = "Alexa.Unit.Distance.Inches"

    # Kilometers
    UNIT_DISTANCE_KILOMETERS = "Alexa.Unit.Distance.Kilometers"

    # Meters, Meter, m
    UNIT_DISTANCE_METERS = "Alexa.Unit.Distance.Meters"

    # Miles, Mile
    UNIT_DISTANCE_MILES = "Alexa.Unit.Distance.Miles"

    # Yards, Yard
    UNIT_DISTANCE_YARDS = "Alexa.Unit.Distance.Yards"

    # Grams, Gram, g
    UNIT_MASS_GRAMS = "Alexa.Unit.Mass.Grams"

    # Kilograms, Kilogram, kg
    UNIT_MASS_KILOGRAMS = "Alexa.Unit.Mass.Kilograms"

    # Percent
    UNIT_PERCENT = "Alexa.Unit.Percent"

    # Celsius, Degrees Celsius, Degrees, C, Centigrade, Degrees Centigrade
    UNIT_TEMPERATURE_CELSIUS = "Alexa.Unit.Temperature.Celsius"

    # Degrees, Degree
    UNIT_TEMPERATURE_DEGREES = "Alexa.Unit.Temperature.Degrees"

    # Fahrenheit, Degrees Fahrenheit, Degrees F, Degrees, F
    UNIT_TEMPERATURE_FAHRENHEIT = "Alexa.Unit.Temperature.Fahrenheit"

    # Kelvin, Degrees Kelvin, Degrees K, Degrees, K
    UNIT_TEMPERATURE_KELVIN = "Alexa.Unit.Temperature.Kelvin"

    # Cubic Feet, Cubic Foot
    UNIT_VOLUME_CUBIC_FEET = "Alexa.Unit.Volume.CubicFeet"

    # Cubic Meters, Cubic Meter, Meters Cubed
    UNIT_VOLUME_CUBIC_METERS = "Alexa.Unit.Volume.CubicMeters"

    # Gallons, Gallon
    UNIT_VOLUME_GALLONS = "Alexa.Unit.Volume.Gallons"

    # Liters, Liter, L
    UNIT_VOLUME_LITERS = "Alexa.Unit.Volume.Liters"

    # Pints, Pint
    UNIT_VOLUME_PINTS = "Alexa.Unit.Volume.Pints"

    # Quarts, Quart
    UNIT_VOLUME_QUARTS = "Alexa.Unit.Volume.Quarts"

    # Ounces, Ounce, oz
    UNIT_WEIGHT_OUNCES = "Alexa.Unit.Weight.Ounces"

    # Pounds, Pound, lbs
    UNIT_WEIGHT_POUNDS = "Alexa.Unit.Weight.Pounds"

    # Close
    VALUE_CLOSE = "Alexa.Value.Close"

    # Delicates, Delicate
    VALUE_DELICATE = "Alexa.Value.Delicate"

    # High
    VALUE_HIGH = "Alexa.Value.High"

    # Low
    VALUE_LOW = "Alexa.Value.Low"

    # Maximum, Max
    VALUE_MAXIMUM = "Alexa.Value.Maximum"

    # Medium, Mid
    VALUE_MEDIUM = "Alexa.Value.Medium"

    # Minimum, Min
    VALUE_MINIMUM = "Alexa.Value.Minimum"

    # Open
    VALUE_OPEN = "Alexa.Value.Open"

    # Quick Wash, Fast Wash, Wash Quickly, Speed Wash
    VALUE_QUICK_WASH = "Alexa.Value.QuickWash"


class AlexaCapabilityResource:
    """Base class for Alexa capabilityResources, modeResources, and presetResources objects.

    Resources objects labels must be unique across all modeResources and presetResources within the same device.
    To provide support for all supported locales, include one label from the AlexaGlobalCatalog in the labels array.
    You cannot use any words from the following list as friendly names:
    https://developer.amazon.com/docs/alexa/device-apis/resources-and-assets.html#names-you-cannot-use

    https://developer.amazon.com/docs/device-apis/resources-and-assets.html#capability-resources
    """

    def __init__(self, labels):
        """Initialize an Alexa resource."""
        self._resource_labels = []
        for label in labels:
            self._resource_labels.append(label)

    def serialize_capability_resources(self):
        """Return capabilityResources object serialized for an API response."""
        return self.serialize_labels(self._resource_labels)

    @staticmethod
    def serialize_configuration():
        """Return ModeResources, PresetResources friendlyNames serialized for an API response."""
        return []

    @staticmethod
    def serialize_labels(resources):
        """Return resource label objects for friendlyNames serialized for an API response."""
        labels = []
        for label in resources:
            if label in AlexaGlobalCatalog.__dict__.values():
                label = {"@type": "asset", "value": {"assetId": label}}
            else:
                label = {"@type": "text", "value": {"text": label, "locale": "en-US"}}

            labels.append(label)

        return {"friendlyNames": labels}


class AlexaModeResource(AlexaCapabilityResource):
    """Implements Alexa ModeResources.

    https://developer.amazon.com/docs/device-apis/resources-and-assets.html#capability-resources
    """

    def __init__(self, labels, ordered=False):
        """Initialize an Alexa modeResource."""
        super().__init__(labels)
        self._supported_modes = []
        self._mode_ordered = ordered

    def add_mode(self, value, labels):
        """Add mode to the supportedModes object."""
        self._supported_modes.append({"value": value, "labels": labels})

    def serialize_configuration(self):
        """Return configuration for ModeResources friendlyNames serialized for an API response."""
        mode_resources = []
        for mode in self._supported_modes:
            result = {
                "value": mode["value"],
                "modeResources": self.serialize_labels(mode["labels"]),
            }
            mode_resources.append(result)

        return {"ordered": self._mode_ordered, "supportedModes": mode_resources}


class AlexaPresetResource(AlexaCapabilityResource):
    """Implements Alexa PresetResources.

    Use presetResources with RangeController to provide a set of friendlyNames for each RangeController preset.

    https://developer.amazon.com/docs/device-apis/resources-and-assets.html#presetresources
    """

    def __init__(self, labels, min_value, max_value, precision, unit=None):
        """Initialize an Alexa presetResource."""
        super().__init__(labels)
        self._presets = []
        self._minimum_value = min_value
        self._maximum_value = max_value
        self._precision = precision
        self._unit_of_measure = None
        if unit in AlexaGlobalCatalog.__dict__.values():
            self._unit_of_measure = unit

    def add_preset(self, value, labels):
        """Add preset to configuration presets array."""
        self._presets.append({"value": value, "labels": labels})

    def serialize_configuration(self):
        """Return configuration for PresetResources friendlyNames serialized for an API response."""
        configuration = {
            "supportedRange": {
                "minimumValue": self._minimum_value,
                "maximumValue": self._maximum_value,
                "precision": self._precision,
            }
        }

        if self._unit_of_measure:
            configuration["unitOfMeasure"] = self._unit_of_measure

        if self._presets:
            preset_resources = []
            for preset in self._presets:
                preset_resources.append(
                    {
                        "rangeValue": preset["value"],
                        "presetResources": self.serialize_labels(preset["labels"]),
                    }
                )
            configuration["presets"] = preset_resources

        return configuration


class AlexaSemantics:
    """Class for Alexa Semantics Object.

    You can optionally enable additional utterances by using semantics. When you use semantics,
    you manually map the phrases "open", "close", "raise", and "lower" to directives.

    Semantics is supported for the following interfaces only: ModeController, RangeController, and ToggleController.

    Semantics stateMappings are only supported for one interface of the same type on the same device. If a device has
    multiple RangeControllers only one interface may use stateMappings otherwise discovery will fail.

    You can support semantics actionMappings on different controllers for the same device, however each controller must
    support different phrases. For example, you can support "raise" on a RangeController, and "open" on a ModeController,
    but you can't support "open" on both RangeController and ModeController. Semantics stateMappings are only supported
    for one interface on the same device.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#semantics-object
    """

    MAPPINGS_ACTION = "actionMappings"
    MAPPINGS_STATE = "stateMappings"

    ACTIONS_TO_DIRECTIVE = "ActionsToDirective"
    STATES_TO_VALUE = "StatesToValue"
    STATES_TO_RANGE = "StatesToRange"

    ACTION_CLOSE = "Alexa.Actions.Close"
    ACTION_LOWER = "Alexa.Actions.Lower"
    ACTION_OPEN = "Alexa.Actions.Open"
    ACTION_RAISE = "Alexa.Actions.Raise"

    STATES_OPEN = "Alexa.States.Open"
    STATES_CLOSED = "Alexa.States.Closed"

    DIRECTIVE_RANGE_SET_VALUE = "SetRangeValue"
    DIRECTIVE_RANGE_ADJUST_VALUE = "AdjustRangeValue"
    DIRECTIVE_TOGGLE_TURN_ON = "TurnOn"
    DIRECTIVE_TOGGLE_TURN_OFF = "TurnOff"
    DIRECTIVE_MODE_SET_MODE = "SetMode"
    DIRECTIVE_MODE_ADJUST_MODE = "AdjustMode"

    def __init__(self):
        """Initialize an Alexa modeResource."""
        self._action_mappings = []
        self._state_mappings = []

    def _add_action_mapping(self, semantics):
        """Add action mapping between actions and interface directives."""
        self._action_mappings.append(semantics)

    def _add_state_mapping(self, semantics):
        """Add state mapping between states and interface directives."""
        self._state_mappings.append(semantics)

    def add_states_to_value(self, states, value):
        """Add StatesToValue stateMappings."""
        self._add_state_mapping(
            {"@type": self.STATES_TO_VALUE, "states": states, "value": value}
        )

    def add_states_to_range(self, states, min_value, max_value):
        """Add StatesToRange stateMappings."""
        self._add_state_mapping(
            {
                "@type": self.STATES_TO_RANGE,
                "states": states,
                "range": {"minimumValue": min_value, "maximumValue": max_value},
            }
        )

    def add_action_to_directive(self, actions, directive, payload):
        """Add ActionsToDirective actionMappings."""
        self._add_action_mapping(
            {
                "@type": self.ACTIONS_TO_DIRECTIVE,
                "actions": actions,
                "directive": {"name": directive, "payload": payload},
            }
        )

    def serialize_semantics(self):
        """Return semantics object serialized for an API response."""
        semantics = {}
        if self._action_mappings:
            semantics[self.MAPPINGS_ACTION] = self._action_mappings
        if self._state_mappings:
            semantics[self.MAPPINGS_STATE] = self._state_mappings

        return semantics
