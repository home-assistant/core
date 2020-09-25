"""Node methods and classes for OpenZWave."""
from openzwavemqtt.const import CommandClass, ValueType

from homeassistant.components.websocket_api.const import (
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
)

from .const import (
    ATTR_CONFIG_PARAMETER,
    ATTR_LABEL,
    ATTR_MAX,
    ATTR_MIN,
    ATTR_OPTIONS,
    ATTR_TYPE,
    ATTR_VALUE,
)


class OZWValidationResponse:
    """Class to hold response for validating an action."""

    def __init__(self, success, payload=None, err_type=None, err_msg=None):
        """Initialize OZWValidationResponse."""
        self.success = success
        self.payload = payload
        self.err_type = err_type
        self.err_msg = err_msg

    @staticmethod
    def process_fail(err_type, err_msg):
        """Process an invalid request."""
        return OZWValidationResponse(False, err_type=err_type, err_msg=err_msg)

    @staticmethod
    def process_fail_on_type(value, new_value):
        """Process an invalid request that fails type validation."""
        return OZWValidationResponse.process_fail(
            ERR_NOT_SUPPORTED,
            (
                f"Configuration parameter type {value.type} does "
                f"not match the value type {type(new_value)}"
            ),
        )

    @staticmethod
    def process_success(payload):
        """Process a valid request."""
        return OZWValidationResponse(True, payload=payload)


def set_config_parameter(manager, instance_id, node_id, parameter_index, new_value):
    """Set config parameter to a node."""
    instance = manager.get_instance(instance_id)
    if not instance:
        return OZWValidationResponse.process_fail(
            ERR_NOT_FOUND, "OZW Instance not found"
        )

    node = instance.get_node(node_id)
    if not node:
        return OZWValidationResponse.process_fail(ERR_NOT_FOUND, "OZW Node not found")

    value = node.get_value(CommandClass.CONFIGURATION, parameter_index)
    if not value:
        return OZWValidationResponse.process_fail(
            ERR_NOT_FOUND,
            "Configuration parameter for OZW Node Instance not found",
        )

    # Bool can be passed in as string or bool
    if value.type == ValueType.BOOL:
        if isinstance(new_value, bool):
            value.send_value(new_value)
            return OZWValidationResponse.process_success(new_value)
        if isinstance(new_value, str):
            if new_value.lower() in ("true", "false"):
                payload = new_value.lower() == "true"
                value.send_value(payload)
                return OZWValidationResponse.process_success(payload)

            return OZWValidationResponse.process_fail(
                ERR_NOT_SUPPORTED,
                "Configuration parameter requires true of false",
            )

        return OZWValidationResponse.process_fail_on_type(value, new_value)

    # List value can be passed in as string or int
    if value.type == ValueType.LIST:
        try:
            new_value = int(new_value)
        except ValueError:
            pass
        if not isinstance(new_value, str) and not isinstance(new_value, int):
            return OZWValidationResponse.process_fail_on_type(value, new_value)

        for option in value.value["List"]:
            if new_value not in (option["Label"], option["Value"]):
                continue
            payload = int(option["Value"])
            value.send_value(payload)
            return OZWValidationResponse.process_success(payload)

        return OZWValidationResponse.process_fail(
            ERR_NOT_SUPPORTED,
            f"Invalid value {new_value} for parameter {parameter_index}",
        )

    # Int, Byte, Short are always passed as int, Decimal should be float
    if value.type in (
        ValueType.INT,
        ValueType.BYTE,
        ValueType.SHORT,
        ValueType.DECIMAL,
    ):
        try:
            if value.type == ValueType.DECIMAL:
                new_value = float(new_value)
            else:
                new_value = int(new_value)
        except ValueError:
            return OZWValidationResponse.process_fail_on_type(value, new_value)
        if (value.max and new_value > value.max) or (
            value.min and new_value < value.min
        ):
            return OZWValidationResponse.process_fail(
                ERR_NOT_SUPPORTED,
                (
                    f"Value {new_value} out of range for parameter "
                    f"{parameter_index} (Min: {value.min} Max: {value.max})"
                ),
            )
        value.send_value(new_value)
        return OZWValidationResponse.process_success(new_value)

    # This will catch BUTTON, STRING, and UNKNOWN ValueTypes
    return OZWValidationResponse.process_fail(
        ERR_NOT_SUPPORTED,
        f"Value type of {value.type} for parameter {parameter_index} not supported",
    )


def get_config_parameters(node):
    """Get config parameter from a node."""
    command_class = node.get_command_class(CommandClass.CONFIGURATION)
    if not command_class:
        return OZWValidationResponse.process_fail(
            ERR_NOT_FOUND, "Configuration parameters for OZW Node Instance not found"
        )

    values = []

    for value in command_class.values():
        value_to_return = {}
        # BUTTON types aren't supported yet, and STRING and UNKNOWN
        # are not valid config parameter types
        if value.read_only or value.type in (
            ValueType.BUTTON,
            ValueType.STRING,
            ValueType.UNKNOWN,
        ):
            continue

        value_to_return = {
            ATTR_LABEL: value.label,
            ATTR_TYPE: value.type.value,
            ATTR_CONFIG_PARAMETER: value.index.value,
        }

        if value.type == ValueType.BOOL:
            value_to_return[ATTR_VALUE] = value.value

        elif value.type == ValueType.LIST:
            value_to_return[ATTR_VALUE] = value.value["Selected"]
            value_to_return[ATTR_OPTIONS] = value.value["List"]

        elif value.type in (
            ValueType.INT,
            ValueType.BYTE,
            ValueType.SHORT,
            ValueType.DECIMAL,
        ):
            value_to_return[ATTR_VALUE] = int(value.value)
            value_to_return[ATTR_MAX] = value.max
            value_to_return[ATTR_MIN] = value.min

        values.append(value_to_return)

    return OZWValidationResponse.process_success(values)
