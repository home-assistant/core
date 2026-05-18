"""Constants for the pylint_home_assistant plugin package."""

from enum import IntEnum, StrEnum


class Platform(StrEnum):
    """Entity platform names.

    Inlined from ``homeassistant.const.Platform`` so the plugin package does
    not depend on the ``homeassistant`` package itself.
    """

    AI_TASK = "ai_task"
    AIR_QUALITY = "air_quality"
    ALARM_CONTROL_PANEL = "alarm_control_panel"
    ASSIST_SATELLITE = "assist_satellite"
    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"
    CALENDAR = "calendar"
    CAMERA = "camera"
    CLIMATE = "climate"
    CONVERSATION = "conversation"
    COVER = "cover"
    DATE = "date"
    DATETIME = "datetime"
    DEVICE_TRACKER = "device_tracker"
    EVENT = "event"
    FAN = "fan"
    GEO_LOCATION = "geo_location"
    HUMIDIFIER = "humidifier"
    IMAGE = "image"
    IMAGE_PROCESSING = "image_processing"
    INFRARED = "infrared"
    LAWN_MOWER = "lawn_mower"
    LIGHT = "light"
    LOCK = "lock"
    MEDIA_PLAYER = "media_player"
    NOTIFY = "notify"
    NUMBER = "number"
    RADIO_FREQUENCY = "radio_frequency"
    REMOTE = "remote"
    SCENE = "scene"
    SELECT = "select"
    SENSOR = "sensor"
    SIREN = "siren"
    STT = "stt"
    SWITCH = "switch"
    TEXT = "text"
    TIME = "time"
    TODO = "todo"
    TTS = "tts"
    UPDATE = "update"
    VACUUM = "vacuum"
    VALVE = "valve"
    WAKE_WORD = "wake_word"
    WATER_HEATER = "water_heater"
    WEATHER = "weather"


ENTITY_COMPONENTS: frozenset[str] = frozenset(p.value for p in Platform)


ANY_PLATFORM = "__any_platform__"
"""Synthetic key used in type hint match dicts for functions on any platform."""


class IntegrationType(StrEnum):
    """Integration types from manifest.json."""

    DEVICE = "device"
    ENTITY = "entity"
    HARDWARE = "hardware"
    HELPER = "helper"
    HUB = "hub"
    SERVICE = "service"
    SYSTEM = "system"
    VIRTUAL = "virtual"


class Module(StrEnum):
    """Well-known integration sub-module names."""

    INIT = "__init__"
    APPLICATION_CREDENTIALS = "application_credentials"
    BACKUP = "backup"
    CAST = "cast"
    CONFIG_FLOW = "config_flow"
    CONST = "const"
    COORDINATOR = "coordinator"
    DEVICE_ACTION = "device_action"
    DEVICE_CONDITION = "device_condition"
    DEVICE_TRIGGER = "device_trigger"
    DIAGNOSTICS = "diagnostics"
    ENTITY = "entity"


class QualityScaleTier(IntEnum):
    """Quality scale tiers, ordered by level."""

    BRONZE = 1
    SILVER = 2
    GOLD = 3
    PLATINUM = 4


class QualityScaleRule(StrEnum):
    """Integration quality scale rule names."""

    # Bronze
    ACTION_SETUP = "action-setup"
    APPROPRIATE_POLLING = "appropriate-polling"
    BRANDS = "brands"
    COMMON_MODULES = "common-modules"
    CONFIG_FLOW = "config-flow"
    CONFIG_FLOW_TEST_COVERAGE = "config-flow-test-coverage"
    DEPENDENCY_TRANSPARENCY = "dependency-transparency"
    DOCS_ACTIONS = "docs-actions"
    DOCS_HIGH_LEVEL_DESCRIPTION = "docs-high-level-description"
    DOCS_INSTALLATION_INSTRUCTIONS = "docs-installation-instructions"
    DOCS_REMOVAL_INSTRUCTIONS = "docs-removal-instructions"
    ENTITY_EVENT_SETUP = "entity-event-setup"
    ENTITY_UNIQUE_ID = "entity-unique-id"
    HAS_ENTITY_NAME = "has-entity-name"
    RUNTIME_DATA = "runtime-data"
    TEST_BEFORE_CONFIGURE = "test-before-configure"
    TEST_BEFORE_SETUP = "test-before-setup"
    UNIQUE_CONFIG_ENTRY = "unique-config-entry"

    # Silver
    ACTION_EXCEPTIONS = "action-exceptions"
    CONFIG_ENTRY_UNLOADING = "config-entry-unloading"
    DOCS_CONFIGURATION_PARAMETERS = "docs-configuration-parameters"
    DOCS_INSTALLATION_PARAMETERS = "docs-installation-parameters"
    ENTITY_UNAVAILABLE = "entity-unavailable"
    INTEGRATION_OWNER = "integration-owner"
    LOG_WHEN_UNAVAILABLE = "log-when-unavailable"
    PARALLEL_UPDATES = "parallel-updates"
    REAUTHENTICATION_FLOW = "reauthentication-flow"
    TEST_COVERAGE = "test-coverage"

    # Gold
    DEVICES = "devices"
    DIAGNOSTICS = "diagnostics"
    DISCOVERY = "discovery"
    DISCOVERY_UPDATE_INFO = "discovery-update-info"
    DOCS_DATA_UPDATE = "docs-data-update"
    DOCS_EXAMPLES = "docs-examples"
    DOCS_KNOWN_LIMITATIONS = "docs-known-limitations"
    DOCS_SUPPORTED_DEVICES = "docs-supported-devices"
    DOCS_SUPPORTED_FUNCTIONS = "docs-supported-functions"
    DOCS_TROUBLESHOOTING = "docs-troubleshooting"
    DOCS_USE_CASES = "docs-use-cases"
    DYNAMIC_DEVICES = "dynamic-devices"
    ENTITY_CATEGORY = "entity-category"
    ENTITY_DEVICE_CLASS = "entity-device-class"
    ENTITY_DISABLED_BY_DEFAULT = "entity-disabled-by-default"
    ENTITY_TRANSLATIONS = "entity-translations"
    EXCEPTION_TRANSLATIONS = "exception-translations"
    ICON_TRANSLATIONS = "icon-translations"
    RECONFIGURATION_FLOW = "reconfiguration-flow"
    REPAIR_ISSUES = "repair-issues"
    STALE_DEVICES = "stale-devices"

    # Platinum
    ASYNC_DEPENDENCY = "async-dependency"
    INJECT_WEBSESSION = "inject-websession"
    STRICT_TYPING = "strict-typing"
