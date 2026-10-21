"""Tests for the action enums checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.actions.service_enums import ServiceEnumsChecker
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

SERVICES_MODULE = "homeassistant.components.test_integration.services"


@pytest.fixture(name="service_enums_checker")
def service_enums_checker_fixture(linter: UnittestLinter) -> ServiceEnumsChecker:
    """Fixture to provide an action enums checker."""
    return ServiceEnumsChecker(linter)


def _find_node(root_node: nodes.Module, line: int, source: str) -> nodes.NodeNG:
    """Return the node on *line* whose source is *source*."""
    return next(
        node
        for node in root_node.nodes_of_class(nodes.NodeNG)
        if node.lineno == line and node.as_string() == source
    )


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
SCHEMA = probatio.Schema({probatio.Required(TestServiceArgument.FIELD): str})

async def _handler(call: ServiceCall) -> None:
    call.data[TestServiceArgument.FIELD]
    call.data.get(TestServiceArgument.OTHER)

@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, TestService.ACTION, _handler, SCHEMA)
""",
            SERVICES_MODULE,
            id="enum_members",
        ),
        pytest.param(
            """
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

async def _handler(call: ServiceCall) -> None:
    call.data[ATTR_CONFIG_ENTRY_ID]
    call.data.get("device_id")

@callback
def async_setup_services(hass):
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        TestService.ACTION,
        entity_domain=SENSOR_DOMAIN,
        schema={
            probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
            probatio.Optional("entity_id"): str,
        },
        func="method",
    )
""",
            SERVICES_MODULE,
            id="shared_fields",
        ),
        pytest.param(
            """
ITEM_SCHEMA = probatio.Schema({probatio.Required("item_key"): str})

SCHEMA = probatio.Schema(
    {
        probatio.Required(TestServiceArgument.ITEMS): [ITEM_SCHEMA],
        probatio.Optional(TestServiceArgument.OPTIONS): {
            probatio.Optional("option_key"): str
        },
    }
)

@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, TestService.ACTION, _handler, SCHEMA)
""",
            SERVICES_MODULE,
            id="nested_schema_keys",
        ),
        pytest.param(
            """
OTHER_SCHEMA = probatio.Schema({probatio.Required("not_an_action"): str})

async def _handler(call: ServiceCall) -> None:
    call.hass.data[DOMAIN]
    entry.data["host"]
""",
            SERVICES_MODULE,
            id="not_action_fields",
        ),
        pytest.param(
            """
async def _handler(call: ServiceCall) -> None:
    for desc in FIELDS:
        call.data[desc.service_field]
    call.data.get(UNKNOWN_CONSTANT)
""",
            SERVICES_MODULE,
            id="dynamic_keys",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    hass.services.async_register(
        DOMAIN, "my_action", _handler, {probatio.Required("field"): str}
    )
""",
            "homeassistant.components.test_integration",
            id="not_services_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    service_enums_checker: ServiceEnumsChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, service_enums_checker, root_node)


@pytest.mark.parametrize(
    ("code", "line", "source"),
    [
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, "my_action", _handler)
""",
            4,
            "'my_action'",
            id="services_async_register",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    async_register_admin_service(hass, DOMAIN, SERVICE_ADMIN, _handler)
""",
            4,
            "SERVICE_ADMIN",
            id="admin_service",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, TestService.ACTION.value, _handler)
""",
            4,
            "TestService.ACTION.value",
            id="enum_member_value",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, TestServices.ACTION, _handler)
""",
            4,
            "TestServices.ACTION",
            id="plural_enum_name",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    service.async_register_platform_entity_service(
        hass, DOMAIN, service_name=SERVICE_ACTION, entity_domain=SENSOR_DOMAIN
    )
""",
            5,
            "SERVICE_ACTION",
            id="platform_entity_service_keyword",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.data[DATA_COMPONENT].async_register_entity_service(
        "my_action", None, "method"
    )
""",
            5,
            "'my_action'",
            id="entity_component",
        ),
    ],
)
def test_action_name_not_enum(
    linter: UnittestLinter,
    service_enums_checker: ServiceEnumsChecker,
    code: str,
    line: int,
    source: str,
) -> None:
    """Test that action names which are not enum members are flagged."""
    root_node = astroid.parse(code, SERVICES_MODULE)
    node = _find_node(root_node, line, source)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-action-name-not-enum",
            node=node,
            line=node.lineno,
            col_offset=node.col_offset,
            end_line=node.end_lineno,
            end_col_offset=node.end_col_offset,
        ),
    ):
        walk_checker(linter, service_enums_checker, root_node)


@pytest.mark.parametrize(
    ("code", "line", "source", "field"),
    [
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.services.async_register(
        DOMAIN, TestService.ACTION, _handler, {probatio.Required("field"): str}
    )
""",
            5,
            "'field'",
            "field",
            id="raw_schema_key",
        ),
        pytest.param(
            """
ATTR_FIELD = "field"
SCHEMA = probatio.Schema({probatio.Optional(ATTR_FIELD): str})

@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, TestService.ACTION, _handler, SCHEMA)
""",
            3,
            "ATTR_FIELD",
            "field",
            id="constant_schema_key",
        ),
        pytest.param(
            """
from enum import StrEnum

class TestServiceArgument(StrEnum):
    FIELD = "field"

@callback
def async_setup_services(hass):
    hass.services.async_register(
        DOMAIN,
        TestService.ACTION,
        _handler,
        {probatio.Required(TestServiceArgument.FIELD.value): str},
    )
""",
            13,
            "TestServiceArgument.FIELD.value",
            "field",
            id="enum_member_value_schema_key",
        ),
        pytest.param(
            """
BASE_SCHEMA = {probatio.Required("base"): str}

@callback
def async_setup_services(hass):
    hass.services.async_register(
        DOMAIN,
        TestService.ACTION,
        _handler,
        probatio.All(
            cv.make_entity_service_schema(
                {**BASE_SCHEMA, probatio.Optional(TestServiceArgument.FIELD): str}
            ),
            _validate,
        ),
    )
""",
            2,
            "'base'",
            "base",
            id="merged_schema_key",
        ),
        pytest.param(
            """
BASE_SCHEMA = probatio.Schema({probatio.Required(TestServiceArgument.FIELD): str})
SCHEMA = BASE_SCHEMA.extend({probatio.Optional("extended"): str})

@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, TestService.ACTION, _handler, SCHEMA)
""",
            3,
            "'extended'",
            "extended",
            id="extended_schema_key",
        ),
        pytest.param(
            """
async def _handler(call: ServiceCall) -> None:
    call.data["field"]
""",
            3,
            "'field'",
            "field",
            id="data_subscript",
        ),
        pytest.param(
            """
ATTR_FIELD = "field"

async def _handler(service_call: core.ServiceCall) -> None:
    service_call.data.get(ATTR_FIELD)
""",
            5,
            "ATTR_FIELD",
            "field",
            id="data_get",
        ),
    ],
)
def test_action_field_not_enum(
    linter: UnittestLinter,
    service_enums_checker: ServiceEnumsChecker,
    code: str,
    line: int,
    source: str,
    field: str,
) -> None:
    """Test that action fields which are not enum members are flagged."""
    root_node = astroid.parse(code, SERVICES_MODULE)
    node = _find_node(root_node, line, source)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-action-field-not-enum",
            node=node,
            args=(field,),
            line=node.lineno,
            col_offset=node.col_offset,
            end_line=node.end_lineno,
            end_col_offset=node.end_col_offset,
        ),
    ):
        walk_checker(linter, service_enums_checker, root_node)
