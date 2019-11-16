"""
Templates for auto-generated Rhasspy voice commands.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
from homeassistant.components.cover import INTENT_CLOSE_COVER, INTENT_OPEN_COVER
from homeassistant.components.light import INTENT_SET
from homeassistant.components.shopping_list import INTENT_ADD_ITEM, INTENT_LAST_ITEMS
from homeassistant.helpers import intent
from homeassistant.helpers.template import Template as T

from .const import (
    INTENT_DEVICE_STATE,
    INTENT_IS_COVER_CLOSED,
    INTENT_IS_COVER_OPEN,
    INTENT_IS_DEVICE_OFF,
    INTENT_IS_DEVICE_ON,
    INTENT_IS_DEVICE_STATE,
    INTENT_SET_TIMER,
    INTENT_TIMER_READY,
    INTENT_TRIGGER_AUTOMATION,
    INTENT_TRIGGER_AUTOMATION_LATER,
    KEY_COMMAND_TEMPLATES,
    KEY_COMMANDS,
    KEY_DATA,
    KEY_DOMAINS,
    KEY_ENTITIES,
    KEY_INCLUDE,
    KEY_REGEX,
)

DEFAULT_API_URL = "http://localhost:12101/api/"
DEFAULT_LANGUAGE = "en-US"
DEFAULT_SLOTS = {
    "light_color": [
        "black",
        "blue",
        "brown",
        "gray",
        "green",
        "pink",
        "purple",
        "violet",
        "red",
        "yellow",
        "orange",
        "white",
    ]
}
DEFAULT_CUSTOM_WORDS = {}
DEFAULT_REGISTER_CONVERSATION = True
DEFAULT_TRAIN_TIMEOUT = 1.0
DEFAULT_SHOPPING_LIST_ITEMS = []
DEFAULT_MAKE_INTENT_COMMANDS = True

DEFAULT_NAME_REPLACE = {
    # English
    # Replace dashes/underscores with spaces
    "en-US": {KEY_REGEX: [{r"[_-]": " "}]},
    #
    # French
    # Split dashed words (est-ce -> est -ce)
    # Replace dashes with spaces
    "fr-FR": {KEY_REGEX: [{r"-": " -"}, {r"_": " "}]},
}

DEFAULT_HANDLE_INTENTS = [
    INTENT_IS_DEVICE_ON,
    INTENT_IS_DEVICE_OFF,
    INTENT_IS_COVER_OPEN,
    INTENT_IS_COVER_CLOSED,
    INTENT_IS_DEVICE_STATE,
    INTENT_DEVICE_STATE,
    INTENT_TRIGGER_AUTOMATION,
    INTENT_TRIGGER_AUTOMATION_LATER,
    INTENT_SET_TIMER,
    INTENT_TIMER_READY,
]

DEFAULT_RESPONSE_TEMPLATES = {
    "en-US": {
        INTENT_IS_DEVICE_ON: T(
            "{{ 'Yes' if entity.state in states else 'No' }}. {{ entity.name }} {{ 'are' if entity.name.endswith('s') else 'is' }} on."
        ),
        INTENT_IS_DEVICE_OFF: T(
            "{{ 'Yes' if entity.state in states else 'No' }}. {{ entity.name }} {{ 'are' if entity.name.endswith('s') else 'is' }} off."
        ),
        INTENT_IS_COVER_OPEN: T(
            "{{ 'Yes' if entity.state in states else 'No' }}. {{ entity.name }} {{ 'are' if entity.name.endswith('s') else 'is' }} open."
        ),
        INTENT_IS_COVER_CLOSED: T(
            "{{ 'Yes' if entity.state in states else 'No' }}. {{ entity.name }} {{ 'are' if entity.name.endswith('s') else 'is' }} closed."
        ),
        INTENT_IS_DEVICE_STATE: T(
            "{{ 'Yes' if entity.state == state else 'No' }}. {{ entity.name }} {{ 'are' if entity.name.endswith('s') else 'is' }} {{ state.replace('_', ' ') }}."
        ),
        INTENT_DEVICE_STATE: T(
            "{{ entity.name }} {% 'are' if entity.name.endswith('s') else 'is' %} {{ entity.state }}."
        ),
        INTENT_TIMER_READY: T("Timer is ready."),
        INTENT_TRIGGER_AUTOMATION: T("Triggered {{ automation.name }}."),
    }
}

DEFAULT_INTENT_STATES = {
    "en-US": {
        INTENT_IS_DEVICE_ON: ["on"],
        INTENT_IS_DEVICE_OFF: ["off"],
        INTENT_IS_COVER_OPEN: ["open"],
        INTENT_IS_COVER_CLOSED: ["closed"],
    }
}

ON_OFF_DOMAINS = ["light", "switch", "camera", "fan", "media_player"]

# Include/exclude domains/entities by intent for auto-generated commands.
DEFAULT_INTENT_FILTERS = {
    intent.INTENT_TURN_ON: {
        KEY_INCLUDE: {KEY_DOMAINS: ON_OFF_DOMAINS, KEY_ENTITIES: ["group.all_lights"]}
    },
    intent.INTENT_TURN_OFF: {
        KEY_INCLUDE: {KEY_DOMAINS: ON_OFF_DOMAINS, KEY_ENTITIES: ["group.all_lights"]}
    },
    intent.INTENT_TOGGLE: {
        KEY_INCLUDE: {KEY_DOMAINS: ON_OFF_DOMAINS, KEY_ENTITIES: ["group.all_lights"]}
    },
    INTENT_OPEN_COVER: {
        KEY_INCLUDE: {KEY_DOMAINS: ["cover"], KEY_ENTITIES: ["group.all_covers"]}
    },
    INTENT_CLOSE_COVER: {
        KEY_INCLUDE: {KEY_DOMAINS: ["cover"], KEY_ENTITIES: ["group.all_covers"]}
    },
    INTENT_SET: {
        KEY_INCLUDE: {KEY_DOMAINS: ["light"], KEY_ENTITIES: ["group.all_lights"]}
    },
    INTENT_DEVICE_STATE: {
        KEY_INCLUDE: {
            KEY_DOMAINS: ["light", "switch", "binary_sensor", "sensor", "cover"],
            KEY_ENTITIES: ["group.all_lights", "group.all_covers"],
        }
    },
    INTENT_IS_DEVICE_ON: {
        KEY_INCLUDE: {KEY_DOMAINS: ON_OFF_DOMAINS, KEY_ENTITIES: ["group.all_lights"]}
    },
    INTENT_IS_DEVICE_OFF: {
        KEY_INCLUDE: {KEY_DOMAINS: ON_OFF_DOMAINS, KEY_ENTITIES: ["group.all_lights"]}
    },
    INTENT_IS_COVER_OPEN: {
        KEY_INCLUDE: {KEY_DOMAINS: ["cover"], KEY_ENTITIES: ["group.all_covers"]}
    },
    INTENT_IS_COVER_CLOSED: {
        KEY_INCLUDE: {KEY_DOMAINS: ["cover"], KEY_ENTITIES: ["group.all_covers"]}
    },
    INTENT_TRIGGER_AUTOMATION: {KEY_INCLUDE: {KEY_DOMAINS: ["automation"]}},
    INTENT_TRIGGER_AUTOMATION_LATER: {KEY_INCLUDE: {KEY_DOMAINS: ["automation"]}},
}

# Default command templates by intent.
# Includes built-in Home Assistant intents as well as Rhasspy intents.
DEFAULT_INTENT_COMMANDS = {
    "en-US": {
        intent.INTENT_TURN_ON: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "turn on [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}}"
                    ),
                    T(
                        "turn [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} on"
                    ),
                ]
            }
        ],
        intent.INTENT_TURN_OFF: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "turn off [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}}"
                    ),
                    T(
                        "turn [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} off"
                    ),
                ]
            }
        ],
        intent.INTENT_TOGGLE: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "toggle [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}}"
                    ),
                    T(
                        "[the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} toggle"
                    ),
                ],
            }
        ],
        INTENT_ADD_ITEM: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "add [the|a|an] ({{ clean_item_name }}){name:{{ item_name }}} to [my] shopping list"
                    )
                ]
            }
        ],
        INTENT_LAST_ITEMS: [
            {
                KEY_COMMANDS: [
                    "what is on my shopping list",
                    "[list | tell me] [my] shopping list [items]",
                ]
            }
        ],
        INTENT_OPEN_COVER: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T("open [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}}"),
                    T("[the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} open"),
                ]
            }
        ],
        INTENT_CLOSE_COVER: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T("close [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}}"),
                    T("[the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} close"),
                ]
            }
        ],
        INTENT_SET: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "set [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} [to] ($light_color){color}"
                    ),
                    T(
                        "set [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} [brightness [to] | to brightness] ($number_0_100){brightness}"
                    ),
                    T(
                        "set [the] brightness [of] [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} [to] ($number_0_100){brightness}"
                    ),
                    T(
                        "set [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} [to] (maximum){brightness:100} brightness"
                    ),
                ]
            }
        ],
        INTENT_DEVICE_STATE: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "what (is | are) [the|a|an] (state | states) of [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}}"
                    ),
                    T(
                        "what [is | are] [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} (state | states)"
                    ),
                ]
            }
        ],
        INTENT_IS_DEVICE_ON: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "(is | are) [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} on"
                    )
                ]
            }
        ],
        INTENT_IS_DEVICE_OFF: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "(is | are) [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} off"
                    )
                ]
            }
        ],
        INTENT_IS_COVER_OPEN: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "(is | are) [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} open"
                    )
                ],
            }
        ],
        INTENT_IS_COVER_CLOSED: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "(is | are) [the|a|an] ({{ speech_name }}){name:{{ friendly_name }}} closed"
                    )
                ]
            }
        ],
        INTENT_IS_DEVICE_STATE: [
            {
                KEY_COMMANDS: ["is it sunset", "has the sun set [yet]"],
                KEY_DATA: {"name": "sun", "state": "below_horizon"},
            }
        ],
        INTENT_TRIGGER_AUTOMATION: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "(run | execute | trigger) [program | automation] ({{ speech_name }}){name:{{ friendly_name }}}"
                    )
                ]
            }
        ],
        INTENT_TRIGGER_AUTOMATION_LATER: [
            {
                KEY_COMMAND_TEMPLATES: [
                    T(
                        "(run | execute | trigger) [program | automation] ({{ speech_name }}){name:{{ friendly_name }}} (in | after) <SetTimer.time_expr>"
                    ),
                    T(
                        "(in | after) <SetTimer.time_expr> (run | trigger) [program | automation] ({{ speech_name }}){name:{{ friendly_name }}}"
                    ),
                ]
            }
        ],
        INTENT_SET_TIMER: [
            {
                KEY_COMMANDS: [
                    "two_to_nine = (two:2 | three:3 | four:4 | five:5 | six:6 | seven:7 | eight:8 | nine:9)",
                    "one_to_nine = (one:1 | <two_to_nine>)",
                    "",
                    "teens = (ten:10 | eleven:11 | twelve:12 | thirteen:13 | fourteen:14 | fifteen:15 | sixteen:16 | seventeen:17 | eighteen:18 | nineteen:19)",
                    "",
                    "tens = (twenty:20 | thirty:30 | forty:40 | fifty:50)",
                    "one_to_nine = (one:1 | <two_to_nine>)",
                    "",
                    "one_to_fifty_nine = (<one_to_nine> | <teens> | <tens> [<one_to_nine>])",
                    "two_to_fifty_nine = (<two_to_nine> | <teens> | <tens> [<one_to_nine>])",
                    "hour_half_expr = (<one_to_nine>{hours} and (a half){{minutes:30}})",
                    "hour_expr = (((one:1){hours}) | ((<one_to_nine>){hours}) | <hour_half_expr>) (hour | hours)",
                    "minute_half_expr = (<one_to_fifty_nine>{minutes} and (a half){{seconds:30}})",
                    "minute_expr = (((one:1){minutes}) | ((<two_to_fifty_nine>){minutes}) | <minute_half_expr>) (minute | minutes)",
                    "second_expr = (((one:1){seconds}) | ((<two_to_fifty_nine>){seconds})) (second | seconds)",
                    "",
                    "time_expr = ((<hour_expr> [[and] <minute_expr>] [[and] <second_expr>]) | (<minute_expr> [[and] <second_expr>]) | <second_expr>)",
                    "",
                    "set [a] timer for <time_expr>",
                ]
            }
        ],
    }
}
