"""Services for Matter devices."""

from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
import voluptuous as vol

from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

from .const import DOMAIN, LOGGER
from .helpers import (
    get_lock_endpoint_from_node,
    get_matter,
    lock_supports_usr_feature,
    node_from_ha_device_id,
)

ATTR_DURATION = "duration"
ATTR_EMERGENCY_BOOST = "emergency_boost"
ATTR_TEMPORARY_SETPOINT = "temporary_setpoint"

# Lock service attributes
ATTR_DEVICE_ID = "device_id"
ATTR_PIN_CODE = "pin_code"
ATTR_USER_NAME = "user_name"
ATTR_USER_INDEX = "user_index"
ATTR_USER_TYPE = "user_type"
ATTR_CREDENTIAL_INDEX = "credential_index"

SERVICE_WATER_HEATER_BOOST = "water_heater_boost"
SERVICE_LOCK_SET_PIN = "lock_set_pin"
SERVICE_LOCK_CLEAR_PIN = "lock_clear_pin"
SERVICE_LOCK_SET_USER = "lock_set_user"
SERVICE_LOCK_CLEAR_USER = "lock_clear_user"

# Lock constants
DEFAULT_MIN_PIN_LENGTH = 4
DEFAULT_MAX_PIN_LENGTH = 8
DEFAULT_MAX_CREDENTIALS = 20
LOCK_COMMAND_TIMEOUT_MS = 1000
CREDENTIAL_STATUS_SUCCESS = 0

# Credential type enum values
CREDENTIAL_TYPE_PIN = 1

# User type mapping for lock services
USER_TYPE_MAP = {
    "unrestricted": 0,
    "year_day_schedule": 1,
    "week_day_schedule": 2,
    "programming": 3,
    "non_access": 4,
    "forced": 5,
    "disposable": 6,
    "expiring": 7,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Matter services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_WATER_HEATER_BOOST,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            # duration >=1
            vol.Required(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(ATTR_EMERGENCY_BOOST): cv.boolean,
            vol.Optional(ATTR_TEMPORARY_SETPOINT): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=65)
            ),
        },
        func="async_set_boost",
    )

    # Lock management services
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOCK_SET_PIN,
        _async_handle_lock_set_pin,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_PIN_CODE): cv.string,
                vol.Optional(ATTR_USER_NAME): cv.string,
                vol.Optional(ATTR_USER_TYPE, default="unrestricted"): vol.In(
                    USER_TYPE_MAP.keys()
                ),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOCK_CLEAR_PIN,
        _async_handle_lock_clear_pin,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_USER_INDEX): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional(ATTR_CREDENTIAL_INDEX): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOCK_SET_USER,
        _async_handle_lock_set_user,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Optional(ATTR_USER_INDEX): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional(ATTR_USER_NAME): cv.string,
                vol.Optional(ATTR_USER_TYPE, default="unrestricted"): vol.In(
                    USER_TYPE_MAP.keys()
                ),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOCK_CLEAR_USER,
        _async_handle_lock_clear_user,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_USER_INDEX): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        ),
    )


def _get_matter_adapter_and_node(
    hass: HomeAssistant, device_id: str
) -> tuple[Any, Any]:
    """Get Matter adapter and node from device ID."""
    # Verify Matter is set up
    if DOMAIN not in hass.data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="matter_not_configured",
        )

    # Look up the device
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )

    # Get the Matter node
    node = node_from_ha_device_id(hass, device_id)
    if node is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_matter_device",
            translation_placeholders={"device_id": device_id},
        )

    # Get the Matter adapter
    matter = get_matter(hass)

    return matter, node


def _get_lock_endpoint(node: Any) -> Any:
    """Get the lock endpoint from a node."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_lock_on_device",
        )

    if not lock_supports_usr_feature(lock_endpoint):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="lock_usr_not_supported",
        )

    return lock_endpoint


async def _find_available_user_slot(
    matter: Any, node: Any, lock_endpoint: Any
) -> int | None:
    """Find the first available user slot on the lock."""
    max_users = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
        )
        or 0
    )

    for idx in range(1, max_users + 1):
        get_user_response = await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(userIndex=idx),
        )
        if getattr(get_user_response, "userStatus", None) is None:
            return idx

    return None


async def _find_available_credential_slot(
    matter: Any, node: Any, lock_endpoint: Any
) -> int | None:
    """Find the first available credential slot on the lock."""
    max_credentials = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.NumberOfPINUsersSupported
        )
        or DEFAULT_MAX_CREDENTIALS
    )

    for cred_idx in range(1, max_credentials + 1):
        check_credential = clusters.DoorLock.Structs.CredentialStruct(
            credentialType=CREDENTIAL_TYPE_PIN,
            credentialIndex=cred_idx,
        )
        status_response = await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetCredentialStatus(
                credential=check_credential,
            ),
        )
        # Default to False (available) if attribute is missing
        if not getattr(status_response, "credentialExists", False):
            return cred_idx

    return None


async def _create_lock_user(
    matter: Any,
    node: Any,
    lock_endpoint: Any,
    user_index: int,
    user_name: str | None,
    user_type_enum: int,
) -> None:
    """Create a new user on the lock."""
    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            userIndex=user_index,
            userName=user_name,
            userUniqueID=None,
            userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
            userType=user_type_enum,
            credentialRule=clusters.DoorLock.Enums.CredentialRuleEnum.kSingle,
        ),
        timed_request_timeout_ms=LOCK_COMMAND_TIMEOUT_MS,
    )


async def _clear_lock_user(
    matter: Any, node: Any, lock_endpoint: Any, user_index: int
) -> None:
    """Clear a user from the lock."""
    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearUser(userIndex=user_index),
        timed_request_timeout_ms=LOCK_COMMAND_TIMEOUT_MS,
    )


def _validate_pin_code(pin_code: str, lock_endpoint: Any) -> bytes:
    """Validate PIN code length and return encoded bytes."""
    min_pin = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MinPINCodeLength
        )
        or DEFAULT_MIN_PIN_LENGTH
    )
    max_pin = (
        lock_endpoint.get_attribute_value(
            None, clusters.DoorLock.Attributes.MaxPINCodeLength
        )
        or DEFAULT_MAX_PIN_LENGTH
    )

    credential_data = pin_code.encode("utf-8")
    if len(credential_data) < min_pin or len(credential_data) > max_pin:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_pin_length",
            translation_placeholders={
                "min_length": str(min_pin),
                "max_length": str(max_pin),
                "actual_length": str(len(credential_data)),
            },
        )

    return credential_data


async def _async_handle_lock_set_pin(call: ServiceCall) -> None:
    """Handle the lock_set_pin service call."""
    hass = call.hass
    device_id = call.data[ATTR_DEVICE_ID]
    pin_code = call.data[ATTR_PIN_CODE]
    user_name = call.data.get(ATTR_USER_NAME)
    user_type_str = call.data.get(ATTR_USER_TYPE, "unrestricted")

    matter, node = _get_matter_adapter_and_node(hass, device_id)
    lock_endpoint = _get_lock_endpoint(node)

    # Validate PIN code
    credential_data = _validate_pin_code(pin_code, lock_endpoint)

    # Find available user slot
    user_index = await _find_available_user_slot(matter, node, lock_endpoint)
    if user_index is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_available_user_slots",
        )

    user_type_enum = USER_TYPE_MAP.get(user_type_str, 0)

    # Create user
    LOGGER.debug("Creating user at index %s with name '%s'", user_index, user_name)
    await _create_lock_user(
        matter, node, lock_endpoint, user_index, user_name, user_type_enum
    )

    # Find available credential slot
    credential_index = await _find_available_credential_slot(
        matter, node, lock_endpoint
    )
    if credential_index is None:
        # Clean up the user we just created
        await _clear_lock_user(matter, node, lock_endpoint, user_index)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_available_credential_slots",
        )

    # Set the credential
    credential = clusters.DoorLock.Structs.CredentialStruct(
        credentialType=CREDENTIAL_TYPE_PIN,
        credentialIndex=credential_index,
    )

    set_response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            credential=credential,
            credentialData=credential_data,
            userIndex=user_index,
            userStatus=None,
            userType=None,
        ),
        timed_request_timeout_ms=LOCK_COMMAND_TIMEOUT_MS,
    )

    raw_status = getattr(set_response, "status", None)
    if raw_status is not None and hasattr(raw_status, "value"):
        raw_status = raw_status.value

    if raw_status != CREDENTIAL_STATUS_SUCCESS:
        # Clean up the user
        await _clear_lock_user(matter, node, lock_endpoint, user_index)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_credential_failed",
        )

    LOGGER.info(
        "Successfully added PIN for user %s (index %s) at credential slot %s",
        user_name or f"User {user_index}",
        user_index,
        credential_index,
    )


async def _async_handle_lock_clear_pin(call: ServiceCall) -> None:
    """Handle the lock_clear_pin service call."""
    hass = call.hass
    device_id = call.data[ATTR_DEVICE_ID]
    user_index = call.data[ATTR_USER_INDEX]
    credential_index = call.data.get(ATTR_CREDENTIAL_INDEX)

    matter, node = _get_matter_adapter_and_node(hass, device_id)
    lock_endpoint = _get_lock_endpoint(node)

    if credential_index:
        # Clear specific credential
        credential = clusters.DoorLock.Structs.CredentialStruct(
            credentialType=CREDENTIAL_TYPE_PIN,
            credentialIndex=credential_index,
        )
        await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.ClearCredential(credential=credential),
            timed_request_timeout_ms=LOCK_COMMAND_TIMEOUT_MS,
        )
        LOGGER.info(
            "Cleared PIN credential at index %s for user %s",
            credential_index,
            user_index,
        )
    else:
        # Clear the entire user (which also clears all their credentials)
        await _clear_lock_user(matter, node, lock_endpoint, user_index)
        LOGGER.info("Cleared user at index %s (including all credentials)", user_index)


async def _async_handle_lock_set_user(call: ServiceCall) -> None:
    """Handle the lock_set_user service call."""
    hass = call.hass
    device_id = call.data[ATTR_DEVICE_ID]
    user_index = call.data.get(ATTR_USER_INDEX)
    user_name = call.data.get(ATTR_USER_NAME)
    user_type_str = call.data.get(ATTR_USER_TYPE, "unrestricted")

    matter, node = _get_matter_adapter_and_node(hass, device_id)
    lock_endpoint = _get_lock_endpoint(node)

    user_type_enum = USER_TYPE_MAP.get(user_type_str, 0)

    if user_index is None:
        # Find available slot
        user_index = await _find_available_user_slot(matter, node, lock_endpoint)
        if user_index is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_available_user_slots",
            )

        # Add new user
        await _create_lock_user(
            matter, node, lock_endpoint, user_index, user_name, user_type_enum
        )
        LOGGER.info("Created user at index %s with name '%s'", user_index, user_name)
    else:
        # Update existing user
        get_user_response = await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(userIndex=user_index),
        )

        if getattr(get_user_response, "userStatus", None) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="user_not_found",
                translation_placeholders={"user_index": str(user_index)},
            )

        # Get existing values for fields not specified
        existing_name = getattr(get_user_response, "userName", None)
        existing_unique_id = getattr(get_user_response, "userUniqueID", None)
        existing_status = getattr(get_user_response, "userStatus", 1)
        existing_rule = getattr(get_user_response, "credentialRule", 0)

        await matter.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetUser(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
                userIndex=user_index,
                userName=user_name if user_name is not None else existing_name,
                userUniqueID=existing_unique_id,
                userStatus=existing_status,
                userType=user_type_enum,
                credentialRule=existing_rule,
            ),
            timed_request_timeout_ms=LOCK_COMMAND_TIMEOUT_MS,
        )
        LOGGER.info("Updated user at index %s", user_index)


async def _async_handle_lock_clear_user(call: ServiceCall) -> None:
    """Handle the lock_clear_user service call."""
    hass = call.hass
    device_id = call.data[ATTR_DEVICE_ID]
    user_index = call.data[ATTR_USER_INDEX]

    matter, node = _get_matter_adapter_and_node(hass, device_id)
    lock_endpoint = _get_lock_endpoint(node)

    await _clear_lock_user(matter, node, lock_endpoint, user_index)

    LOGGER.info("Cleared user at index %s", user_index)
