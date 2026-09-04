"""Validate the device type vocabulary and per-integration trait mappings.

The vocabulary is owned by the `homeassistant` integration and defines the known
device types and the traits each is composed of. Each device type is a pair of
files under homeassistant/components/homeassistant/device_types/, where the path
is the device type: appliance/espresso_machine.yaml holds the structure and the
untranslated descriptions written for language models, and
appliance/espresso_machine.strings.json holds the translatable display names.

Integrations may ship a device_types.yaml that maps their own entities onto
those traits. They cannot define device types or traits of their own.

API surface only; the validation is not implemented yet.
"""

import re

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

from .model import Config, Integration
from .translations import translation_key_validator

VOCABULARY_INTEGRATION = "homeassistant"
VOCABULARY_DIR = "device_types"
DEFINITION_SUFFIX = ".yaml"
STRINGS_SUFFIX = ".strings.json"
MAPPING_FILENAME = "device_types.yaml"

DEVICE_TYPE_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


def device_type_validator(value: str) -> str:
    """Validate a device type, a dotted namespace such as appliance.espresso_machine."""
    if not DEVICE_TYPE_PATTERN.match(value):
        raise vol.Invalid(
            f"Device type '{value}' must be a dotted lowercase namespace, "
            "for example 'appliance.espresso_machine'"
        )
    return value


TRAIT_SCHEMA = vol.Schema(
    {
        vol.Required("description"): str,
        vol.Optional("required", default=False): bool,
        vol.Required("domains"): vol.All([vol.Coerce(Platform)], vol.Length(min=1)),
        vol.Optional("device_class"): str,
    }
)

# One device type per file; the type itself comes from the file's path. The
# descriptions here are handed to language models and are not translated.
DEVICE_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required("description"): str,
        vol.Required("traits"): cv.schema_with_slug_keys(
            TRAIT_SCHEMA, slug_validator=translation_key_validator
        ),
    }
)

# The strings file sitting next to each definition, holding only what Voice
# speaks and the frontend shows. Aliases are extra spoken forms Assist should
# also match, on the device type and on individual traits.
ALIASES_SCHEMA = vol.All([str], vol.Length(min=1))

STRINGS_SCHEMA = vol.Schema(
    {
        vol.Required("name"): str,
        vol.Optional("aliases"): ALIASES_SCHEMA,
        vol.Required("traits"): cv.schema_with_slug_keys(
            {
                vol.Required("name"): str,
                vol.Optional("aliases"): ALIASES_SCHEMA,
            },
            slug_validator=translation_key_validator,
        ),
    }
)

MAPPING_SCHEMA = vol.Schema(
    {
        device_type_validator: {
            vol.Required("entity"): cv.schema_with_slug_keys(
                cv.schema_with_slug_keys(
                    cv.string, slug_validator=translation_key_validator
                ),
                slug_validator=vol.Coerce(Platform),
            )
        }
    }
)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate the vocabulary and every integration's trait mapping.

    Beyond the schemas above this checks that:
    - every definition has a strings file beside it, and the two agree on the
      exact set of traits
    - every device type a mapping refers to exists in the vocabulary
    - every trait a mapping refers to is defined for that device type
    - the entity domain a trait is mapped from is allowed for that trait
    """
    raise NotImplementedError
