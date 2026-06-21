"""Tests for the error propagation checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.actions.swallowed_exceptions import (
    SwallowedActionExceptionsChecker,
)
import pytest

from tests.pylint import assert_no_messages


@pytest.fixture(name="error_propagation_checker")
def error_propagation_checker_fixture(
    linter: UnittestLinter,
) -> SwallowedActionExceptionsChecker:
    """Fixture to provide an error propagation checker."""
    return SwallowedActionExceptionsChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError as err:
            raise HomeAssistantError("Failed") from err
""",
            id="raises_homeassistant_error",
        ),
        pytest.param(
            """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError as err:
            raise ServiceValidationError("Invalid") from err
""",
            id="raises_service_validation_error",
        ),
        pytest.param(
            """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        await self.device.turn_on()
""",
            id="no_try_except_at_all",
        ),
        pytest.param(
            """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError:
            raise
""",
            id="bare_raise",
        ),
        pytest.param(
            """
class MySwitch(SwitchEntity):
    def helper_method(self) -> None:
        try:
            self.device.do_something()
        except DeviceError:
            _LOGGER.error("Failed")
""",
            id="non_action_method_ignored",
        ),
        pytest.param(
            """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError:
            _LOGGER.error("Failed")
            raise HomeAssistantError("Failed")
""",
            id="logs_and_raises",
        ),
        pytest.param(
            """
class ApiClient:
    async def async_turn_on(self) -> None:
        try:
            await self.api.enable()
        except ApiError:
            _LOGGER.error("Failed")
""",
            id="non_entity_class_no_bases_ignored",
        ),
        pytest.param(
            """
async def async_turn_on():
    try:
        await api.enable()
    except ApiError:
        _LOGGER.error("Failed")
""",
            id="standalone_function_matching_platform_name_ignored",
        ),
        pytest.param(
            """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        def _callback():
            try:
                do_something()
            except DeviceError:
                _LOGGER.error("Nested failure")
        await self.device.turn_on(callback=_callback)
""",
            id="nested_function_not_flagged",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.switch")
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_log_only_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that logging without raising is flagged."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError:
            _LOGGER.error("Failed to turn on")
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-action-swallowed-exception"
    assert messages[0].args == ("async_turn_on",)


def test_log_and_return_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that logging then returning is flagged."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError as error:
            _LOGGER.error(error)
            return
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_except_pass_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that except with only pass is flagged."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError:
            pass
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("async_turn_on",)


def test_try_except_inside_with_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that try/except inside a with block is caught."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        with some_context():
            try:
                await self.device.turn_on()
            except DeviceError:
                _LOGGER.error("Failed")
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("async_turn_on",)


def test_try_except_inside_async_with_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that try/except inside an async with block is caught."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        async with some_context():
            try:
                await self.device.turn_on()
            except DeviceError:
                _LOGGER.error("Failed")
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_try_except_inside_async_for_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that try/except inside an async for block is caught."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        async for item in some_iterable():
            try:
                await self.device.turn_on(item)
            except DeviceError:
                _LOGGER.error("Failed")
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_exception_handler_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that _LOGGER.exception without raising is flagged."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError:
            _LOGGER.exception("Failed to turn on")
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_multiple_action_methods(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that multiple bad methods are each flagged."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError:
            _LOGGER.error("Failed")

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.device.turn_off()
        except DeviceError:
            _LOGGER.error("Failed")
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2


def test_contextlib_suppress_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that contextlib.suppress in action methods is flagged."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        with contextlib.suppress(DeviceError):
            await self.device.turn_on()
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("async_turn_on",)


def test_bare_suppress_not_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that bare suppress() (not contextlib.suppress) is not flagged."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_off(self, **kwargs) -> None:
        with suppress(DeviceError):
            await self.device.turn_off()
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_decorator_swallows_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that decorators that swallow exceptions are flagged."""
    root_node = astroid.parse(
        """
def my_error_handler(func):
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except DeviceError:
            _LOGGER.error("Device error")
    return wrapper

class MySwitch(SwitchEntity):
    @my_error_handler
    async def async_turn_on(self, **kwargs) -> None:
        await self.device.turn_on()
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("async_turn_on",)


def test_decorator_factory_swallows_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that decorator factories that swallow exceptions are flagged."""
    root_node = astroid.parse(
        """
def my_error_handler(override=False):
    def _decorator(func):
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except DeviceError:
                _LOGGER.error("Device error")
        return wrapper
    return _decorator

class MySwitch(SwitchEntity):
    @my_error_handler(override=True)
    async def async_turn_on(self, **kwargs) -> None:
        await self.device.turn_on()
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_decorator_raises_ha_error_ok(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that decorators that properly raise HomeAssistantError pass."""
    root_node = astroid.parse(
        """
def convert_error(func):
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except DeviceError as err:
            raise HomeAssistantError("Failed") from err
    return wrapper

class MySwitch(SwitchEntity):
    @convert_error
    async def async_turn_on(self, **kwargs) -> None:
        await self.device.turn_on()
""",
        "homeassistant.components.test_integration.switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_custom_service_method_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that custom registered service methods are also checked."""
    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry, async_add_entities):
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_speed",
        {vol.Required("speed"): cv.string},
        "async_set_speed",
    )

class MyFan(FanEntity):
    async def async_set_speed(self, speed: str) -> None:
        try:
            await self.device.set_speed(speed)
        except DeviceError:
            _LOGGER.error("Failed to set speed")
""",
        "homeassistant.components.test_integration.fan",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("async_set_speed",)


def test_custom_service_method_good(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that custom service methods with proper error handling pass."""
    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry, async_add_entities):
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_speed",
        {vol.Required("speed"): cv.string},
        "async_set_speed",
    )

class MyFan(FanEntity):
    async def async_set_speed(self, speed: str) -> None:
        try:
            await self.device.set_speed(speed)
        except DeviceError as err:
            raise HomeAssistantError("Failed") from err
""",
        "homeassistant.components.test_integration.fan",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_unregistered_custom_method_ignored(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that random methods not registered as services are ignored."""
    root_node = astroid.parse(
        """
class MyFan(FanEntity):
    async def async_do_something(self) -> None:
        try:
            await self.device.do_something()
        except DeviceError:
            _LOGGER.error("Failed")
""",
        "homeassistant.components.test_integration.fan",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_standalone_service_handler_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test standalone service handlers via hass.services are checked."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    hass.services.async_register(DOMAIN, "do_thing", _handle_do_thing)

async def _handle_do_thing(call):
    try:
        await some_api.do_thing(call.data["target"])
    except ApiError:
        _LOGGER.error("Failed to do thing")
""",
        "homeassistant.components.test_integration.services",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("_handle_do_thing",)


def test_admin_service_handler_flagged(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that admin service handlers are also checked."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    async_register_admin_service(hass, DOMAIN, "reset", _handle_reset)

async def _handle_reset(call):
    try:
        await some_api.reset()
    except ApiError:
        _LOGGER.error("Failed to reset")
""",
        "homeassistant.components.test_integration.services",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("_handle_reset",)


def test_standalone_service_handler_good(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that standalone handlers with proper error propagation pass."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    hass.services.async_register(DOMAIN, "do_thing", _handle_do_thing)

async def _handle_do_thing(call):
    try:
        await some_api.do_thing(call.data["target"])
    except ApiError as err:
        raise HomeAssistantError("Failed") from err
""",
        "homeassistant.components.test_integration.services",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_not_integration_module_ignored(
    linter: UnittestLinter,
    error_propagation_checker: SwallowedActionExceptionsChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        """
class MySwitch(SwitchEntity):
    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.device.turn_on()
        except DeviceError:
            _LOGGER.error("Failed")
""",
        "tests.components.test_integration.test_switch",
    )
    walker = ASTWalker(linter)
    walker.add_checker(error_propagation_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
