"""Constants for Awtrix time."""

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

DOMAIN = "awtrix3"

DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 1

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR,
                             Platform.BUTTON,
                             Platform.LIGHT,
                             Platform.SENSOR,
                             Platform.SWITCH, ]

COORDINATORS = "coordinators"

# Services
SERVICE_PUSH_APP_DATA = "push_app_data"
SERVICE_SETTINGS = "settings"
SERVICE_SWITCH_APP = "switch_app"
SERVICE_SOUND = "sound"
SERVICE_RTTTL = "rtttl"

SERVICES = [
    SERVICE_PUSH_APP_DATA,
    SERVICE_SETTINGS,
    SERVICE_SOUND,
    SERVICE_RTTTL,
    SERVICE_SWITCH_APP,
]

SERVICE_DATA = "data"
SERVICE_APP_NAME = "name"
CONF_DEVICE_ID = "device_id"

# Schemas
SERVICE_BASE_SCHEMA = vol.Schema(
    {
        # vol.Optional(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DEVICE_ID): vol.All(
            cv.ensure_list
        ),

    }
)

SERVICE_PUSH_APP_DATA_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Required(SERVICE_APP_NAME): str,
        vol.Required(SERVICE_DATA, default={}): dict
    },
)

SERVICE_SWITCH_APP_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Required(SERVICE_APP_NAME): str,
    },
)

SERVICE_RTTTL_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Required(SERVICE_RTTTL): str,
    },
)

SERVICE_SOUND_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Required(SERVICE_SOUND): str,
    },
)

SERVICE_SETTINGS_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
    }, extra=vol.ALLOW_EXTRA,
)

# Fields
SERVICE_RTTTL_FIELDS = {
    "rtttl": {
        "description": "The rtttl text",
        "required": True,
        "example": "two_short:d=4,o=5,b=100:16e6,16e6",
        "selector": {
            "text": ""
        }
    },
    "device_id": {
        "description": "device or list of devices",
        "required": True,
        "example": "deadbeaf",
        "selector": {
            "device": {
                "integration": "awtrix3",
                "multiple" : True,
            }
        }
    }
}

SERVICE_SOUND_FIELDS = {
    "sound": {
        "description": "The sound name",
        "required": True,
        "example": "beep",
        "selector": {
            "text": ""
        }
    },
    "device_id": {
        "description": "device or list of devices",
        "required": True,
        "example": "deadbeaf",
        "selector": {
            "device": {
                "integration": "awtrix3",
                "multiple" : True,
            }
        }
    }
}

SERVICE_PUSH_APP_DATA_FIELDS = {
    "name": {
        "description": "The application name",
        "required": True,
        "example": "Test",
        "selector": {
            "text": ""
        }
    },
    "data": {
        "example": 'text : "Hello, AWTRIX Light!"\nrainbow: true\nicon: "87"\nduration: 5\npushIcon: 2\nlifetime: 900\nrepeat: 1',
        "selector": {
            "object": ""
        }
    },
    "device_id": {
        "description": "device or list of devices",
        "required": True,
        "example": "deadbeaf",
        "selector": {
            "device": {
                "integration": "awtrix3",
                "multiple" : True,
            }
        }
    }
}

SERVICE_SWITCH_APP_FIELDS = {
    "name": {
        "description": "The application name",
        "required": True,
        "example": "Test",
        "selector": {
            "text": ""
        }
    },
    "device_id": {
        "description": "device or list of devices",
        "required": True,
        "example": "deadbeaf",
        "selector": {
            "device": {
                "integration": "awtrix3",
                "multiple" : True,
            }
        }
    }
}

SERVICE_SETTINGS_FIELDS = {
    "ABRI": {
        "example": 'true',
    },
    "ATRANS": {
        "example": 'true',
    },
    "device_id": {
        "description": "device or list of devices",
        "required": True,
        "example": "deadbeaf",
        "selector": {
            "device": {
                "integration": "awtrix3",
                "multiple" : True,
            }
        }
    }
}

# services fields and schemas
SERVICE_TO_FIELDS = {
    SERVICE_PUSH_APP_DATA: SERVICE_PUSH_APP_DATA_FIELDS,
    SERVICE_SETTINGS: SERVICE_SETTINGS_FIELDS,
    SERVICE_SWITCH_APP: SERVICE_SWITCH_APP_FIELDS,
    SERVICE_RTTTL: SERVICE_RTTTL_FIELDS,
    SERVICE_SOUND: SERVICE_SOUND_FIELDS
}

SERVICE_TO_SCHEMA = {
    SERVICE_PUSH_APP_DATA: SERVICE_PUSH_APP_DATA_SCHEMA,
    SERVICE_SETTINGS: SERVICE_SETTINGS_SCHEMA,
    SERVICE_SWITCH_APP: SERVICE_SWITCH_APP_SCHEMA,
    SERVICE_RTTTL: SERVICE_RTTTL_SCHEMA,
    SERVICE_SOUND: SERVICE_SOUND_SCHEMA
}
