"""Common methods used across tests for VeSync."""
import json

from homeassistant.components.vesync.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import load_fixture

FAN_MODEL = "FAN_MODEL"
HUMIDIFIER_MODEL = "HUMIDIFIER_MODEL"


def get_entities(hass: HomeAssistant, identifier: str) -> list:
    """Load entities for devices."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, identifier)})
    assert device is not None

    entity_registry = er.async_get(hass)
    entities: list = er.async_entries_for_device(
        entity_registry, device_id=device.id, include_disabled_entities=True
    )
    assert entities is not None
    return entities


def get_states(hass: HomeAssistant, entities: list) -> list:
    """Load states for entities."""
    states = []
    for entity_entry in entities:
        state = hass.states.get(entity_entry.entity_id)
        assert state
        state_dict = dict(state.as_dict())
        for key in ["context", "last_changed", "last_updated"]:
            state_dict.pop(key)
        states.append(state_dict)
    states.sort(key=lambda x: x["entity_id"])
    return states


def call_api_side_effect__no_devices(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    elif args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture("vesync_api_call__devices__no_devices.json", "vesync")
            ),
            200,
        )
    else:
        raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")


def call_api_side_effect__single_humidifier(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    elif args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__devices__single_humidifier.json", "vesync"
                )
            ),
            200,
        )
    elif args[0] == "/cloud/v2/deviceManaged/bypassV2" and kwargs["method"] == "post":
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__device_details__single_humidifier.json", "vesync"
                )
            ),
            200,
        )
    else:
        raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")


def call_api_side_effect__single_fan(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    elif args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture("vesync_api_call__devices__single_fan.json", "vesync")
            ),
            200,
        )
    elif (
        args[0] == "/131airPurifier/v1/device/deviceDetail"
        and kwargs["method"] == "post"
    ):
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__device_details__single_fan.json", "vesync"
                )
            ),
            200,
        )
    else:
        raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")
