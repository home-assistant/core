DOMAIN = "synapse"
EVENT_NAMESPACE = "digital_alchemy"
PLATFORMS: list[str] = [
    # "alarm_control_panel",
    "binary_sensor",
    "button",
    "climate",
    "cover",
    "date",
    "datetime",
    "fan",
    "humidifier",
    "image",
    "light",
    "lock",
    "number",
    "remote",
    "scene",
    "select",
    "sensor",
    "siren",
    "switch",
    "text",
    "time",
    "update",
    "valve",
    # "camera",
    # "lawn_mower",
    # "media_player",
    # "notify",
    # "todo_list",
    # "vacuum",
    # "water_heater",
]

class SynapseMetadata:
    """Entity device information for device registry."""
    configuration_url: str | None
    default_manufacturer: str
    default_model: str
    default_name: str
    unique_id: str | None
    manufacturer: str | None
    model: str | None
    name: str | None
    serial_number: str | None
    suggested_area: str | None
    sw_version: str | None
    hw_version: str | None

class SynapseApplication:
    """Description of application state"""
    hostname: str
    name: str
    unique_id: str
    username: str
    version: str
    app: str
    device: SynapseMetadata
    hash: str
    sensor: list[object]
    secondary_devices: list[SynapseMetadata]
    boot: str
    title: str

class SynapseBaseEntity:
    attributes: object
    device_class: str | None = None
    entity_category: str | None = None
    icon: str | None = None
    unique_id: str
    name: str
    state: str | int | None = None
    suggested_object_id: str
    supported_features: int
    translation_key: str | None = None


class SynapseButtonDefinition(SynapseBaseEntity):
    pass


class SynapseAlarmControlPanelDefinition(SynapseBaseEntity):
    changed_by: str
    code_format: str
    code_arm_required: bool


class SynapseBinarySensorDefinition(SynapseBaseEntity):
    pass


class SynapseClimateDefinition(SynapseBaseEntity):
    pass


class SynapseCoverDefinition(SynapseBaseEntity):
    pass


class SynapseDateDefinition(SynapseBaseEntity):
    pass


class SynapseDateTimeDefinition(SynapseBaseEntity):
    pass


class SynapseFanDefinition(SynapseBaseEntity):
    pass


class SynapseHumidifierDefinition(SynapseBaseEntity):
    pass


class SynapseImageDefinition(SynapseBaseEntity):
    pass


class SynapseLawnMowerDefinition(SynapseBaseEntity):
    pass


class SynapseLightDefinition(SynapseBaseEntity):
    pass


class SynapseLockDefinition(SynapseBaseEntity):
    pass


class SynapseMediaPlayerDefinition(SynapseBaseEntity):
    pass


class SynapseNotifyDefinition(SynapseBaseEntity):
    pass


class SynapseNumberDefinition(SynapseBaseEntity):
    max_value: float
    min_value: float
    mode: str
    state: float
    step: float


class SynapseRemoteDefinition(SynapseBaseEntity):
    pass


class SynapseSceneDefinition(SynapseBaseEntity):
    pass


class SynapseSelectDefinition(SynapseBaseEntity):
    pass


class SynapseSensorDefinition(SynapseBaseEntity):
    capability_attributes: int
    state_class: str
    native_unit_of_measurement: str
    suggested_display_precision: int
    last_reset: str
    options: list[str]
    unit_of_measurement: str


class SynapseSirenDefinition(SynapseBaseEntity):
    pass


class SynapseSwitchDefinition(SynapseBaseEntity):
    pass


class SynapseTextDefinition(SynapseBaseEntity):
    pass


class SynapseTimeDefinition(SynapseBaseEntity):
    pass


class SynapseTodoListDefinition(SynapseBaseEntity):
    pass


class SynapseUpdateDefinition(SynapseBaseEntity):
    pass


class SynapseVacuumDefinition(SynapseBaseEntity):
    pass


class SynapseValveDefinition(SynapseBaseEntity):
    pass


class SynapseWaterHeaterDefinition(SynapseBaseEntity):
    pass

class SynapseCameraDefinition(SynapseBaseEntity):
    pass
