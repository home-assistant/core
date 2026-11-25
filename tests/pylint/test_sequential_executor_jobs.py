"""Tests for the sequential executor jobs checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.sequential_executor_jobs import (
    SequentialExecutorJobsChecker,
)
import pytest

from . import assert_no_messages, walk_checker


@pytest.fixture(name="executor_checker")
def executor_checker_fixture(
    linter: UnittestLinter,
) -> SequentialExecutorJobsChecker:
    """Fixture to provide a sequential executor jobs checker."""
    return SequentialExecutorJobsChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(blocking_call)
""",
            id="single_call",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    async_do_something(hass)
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_async_api_call",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    if condition:
        pass
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_control_flow",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await get_instance(hass).async_add_executor_job(call_b)
""",
            id="different_executors",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_add_import_executor_job(call_b)
""",
            id="default_and_import_executor",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    result = (await hass.async_add_executor_job(call_b)) + (await other())
""",
            id="nested_with_other_await",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.loop.run_in_executor(custom_executor, call_b)
""",
            id="run_in_custom_executor",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_do_something_else()
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_other_await",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    pending = (await hass.async_add_executor_job(fn) for fn in funcs)
    await hass.async_add_executor_job(call_b)
""",
            id="deferred_generator_body",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    hass.states.async_set("sensor.a", await hass.async_add_executor_job(call_a))
    await hass.async_add_executor_job(call_b)
""",
            id="executor_result_passed_to_async_api",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    task = asyncio.create_task(coro())
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_create_task",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    loop = asyncio.get_running_loop()
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_get_running_loop",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    items = [item async for item in stream]
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_async_comprehension",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    items = [x async for x in stream] + await hass.async_add_executor_job(call_b)
""",
            id="executor_job_with_async_comprehension",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await loop.run_in_executor(pool, call_a)
    pool = another_pool
    await loop.run_in_executor(pool, call_b)
""",
            id="executor_rebound",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await self._instance.async_add_executor_job(call_a)
    self._instance = get_instance(hass)
    await self._instance.async_add_executor_job(call_b)
""",
            id="receiver_rebound",
        ),
        pytest.param(
            """
async def async_gen(hass):
    await hass.async_add_executor_job(call_a)
    yield value
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_yield",
        ),
        pytest.param(
            """
async def async_gen(hass):
    await hass.async_add_executor_job(call_a)
    yield await hass.async_add_executor_job(call_b)
    await hass.async_add_executor_job(call_c)
""",
            id="executor_job_yielded",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    task = asyncio.current_task()
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_current_task",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    get_loop = lambda loop=asyncio.get_running_loop(): loop
    await hass.async_add_executor_job(call_b)
""",
            id="loop_only_call_in_lambda_default",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await loop.run_in_executor(pools[index], call_a)
    index += 1
    await loop.run_in_executor(pools[index], call_b)
""",
            id="executor_index_rebound",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    pool = await loop.run_in_executor(pool, make_pool)
    await loop.run_in_executor(pool, call_b)
""",
            id="executor_rebound_by_job",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await loop.run_in_executor(default, call_b)
""",
            id="executor_named_default",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    future = asyncio.Future()
    await hass.async_add_executor_job(call_b)
""",
            id="future_between_jobs",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    cm = asyncio.timeout(10)
    await hass.async_add_executor_job(call_b)
""",
            id="timeout_between_jobs",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    hass._async_add_hass_job(job)
    await hass.async_add_executor_job(call_b)
""",
            id="private_async_call_between_jobs",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await loop.run_in_executor(pools[0], call_a)
    pools[0] = other_pool
    await loop.run_in_executor(pools[0], call_b)
""",
            id="executor_subscript_reassigned",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration")

    with assert_no_messages(linter):
        walk_checker(linter, executor_checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    result = do_something()
    _LOGGER.debug("Result: %s", result)
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_sync_statements",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    data = await hass.async_add_executor_job(call_a)
    enabled = (await hass.async_add_executor_job(call_b)) == "1"
""",
            id="nested_in_expression",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    items = []
    items += await hass.async_add_executor_job(call_a)
    items += await hass.async_add_executor_job(call_b)
""",
            id="augmented_assignment",
        ),
        pytest.param(
            """
class Coordinator:
    async def _async_update_data(self):
        await self.hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
""",
            id="hass_and_self_hass",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await asyncio.to_thread(call_b)
""",
            id="to_thread",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.loop.run_in_executor(None, call_b)
""",
            id="run_in_default_executor",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_import_executor_job(call_a)
    await hass.async_add_import_executor_job(call_b)
""",
            id="import_executor",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    instance = get_instance(hass)
    await instance.async_add_executor_job(call_a)
    await instance.async_add_executor_job(call_b)
""",
            id="same_custom_executor",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    match value:
        case 1:
            await hass.async_add_executor_job(call_a)
            await hass.async_add_executor_job(call_b)
""",
            id="inside_match",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    try:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
    except* ValueError:
        pass
""",
            id="inside_try_star",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await loop.run_in_executor(pool, call_a)
    other = another_pool
    await loop.run_in_executor(pool, call_b)
""",
            id="unrelated_assignment_with_custom_executor",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    values = list(x for x in items)
    await hass.async_add_executor_job(call_b)
""",
            id="separated_by_sync_generator",
        ),
    ],
)
def test_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
    code: str,
) -> None:
    """Test cases that should trigger a single warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration")
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_two_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that two sequential executor jobs are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_three_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that three sequential executor jobs flag the second and third."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_add_executor_job(call_b)
    await hass.async_add_executor_job(call_c)
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 2


def test_assigned_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that assigned sequential executor jobs are also flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    result_a = await hass.async_add_executor_job(call_a)
    result_b = await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_inside_try_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside a try block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    try:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
    except Exception:
        pass
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_inside_except_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside an except block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    try:
        pass
    except Exception:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_inside_finally_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside a finally block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    try:
        pass
    finally:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_inside_for_else_block_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that sequential calls inside a for/else block are flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    for item in items:
        pass
    else:
        await hass.async_add_executor_job(call_a)
        await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


def test_return_await_sequential_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that return await following an executor job is flagged."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    return await hass.async_add_executor_job(call_b)
""",
        "homeassistant.components.test_integration",
    )
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-sequential-executor-jobs"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await hass.async_add_executor_job(call_a, item)
""",
            id="for_loop",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    async for group in groups:
        for item in group:
            await hass.async_add_executor_job(call_a, item)
""",
            id="for_loop_in_async_for",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    while await hass.async_add_executor_job(has_more):
        result = do_something()
""",
            id="while_test",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        if item:
            results.append(await hass.async_add_executor_job(call_a, item))
""",
            id="nested_in_expression",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        for sub_item in item:
            await hass.async_add_executor_job(call_a, sub_item)
""",
            id="nested_loops_flag_outer_only",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        try:
            await hass.async_add_executor_job(call_a, item)
        except ValueError:
            break
""",
            id="try_and_break",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        @callback
        def handle(value=None):
            pass
        await hass.async_add_executor_job(call_a, item, handle)
""",
            id="nested_function_definition",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await loop.run_in_executor(pool, call_a, item)
""",
            id="same_custom_executor",
        ),
    ],
)
def test_executor_job_in_loop_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
    code: str,
) -> None:
    """Test loops that should trigger a single warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration")
    walk_checker(linter, executor_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-executor-job-in-loop"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def async_setup(hass, config):
    async for item in items:
        await hass.async_add_executor_job(call_a, item)
""",
            id="async_for",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await hass.async_add_executor_job(call_a, item)
        await fetch(item)
""",
            id="other_await",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        if await hass.async_add_executor_job(call_a, item):
            return item
""",
            id="return",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await hass.async_add_executor_job(call_a, item)
        async_dispatcher_send(hass, "signal")
""",
            id="async_api_call",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await hass.async_add_executor_job(call_a, item)
        await get_instance(hass).async_add_executor_job(call_b, item)
""",
            id="different_executors",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await hass.async_add_executor_job(call_a, item)
        values = [value async for value in stream]
""",
            id="async_comprehension",
        ),
        pytest.param(
            """
async def async_gen(hass):
    for item in items:
        yield await hass.async_add_executor_job(call_a, item)
""",
            id="yield",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        def inner():
            return await_me()
        do_something(inner)
""",
            id="no_executor_job",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        async def work():
            await hass.async_add_executor_job(call_a, item)
        workers.append(work)
""",
            id="deferred_function_body",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for pool in pools:
        await loop.run_in_executor(pool, call_a)
""",
            id="executor_rebound_by_target",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for entry in entries:
        instance = get_instance(entry)
        await instance.async_add_executor_job(call_a)
""",
            id="receiver_rebound_in_body",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for index in range(len(pools)):
        await loop.run_in_executor(pools[index], call_a)
""",
            id="executor_index_rebound_by_target",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await hass.async_add_executor_job(call_a, item)
        tasks = asyncio.all_tasks()
""",
            id="all_tasks",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for default in pools:
        await loop.run_in_executor(default, call_a)
""",
            id="executor_named_default_rebound_by_target",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await hass.async_add_executor_job(call_a, item)

        class Helper:
            loop = asyncio.get_running_loop()
""",
            id="loop_only_call_in_class_body",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    for item in items:
        await loop.run_in_executor(pools[0], call_a, item)
        del pools[0]
""",
            id="executor_subscript_deleted",
        ),
    ],
)
def test_executor_job_in_loop_not_flagged(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
    code: str,
) -> None:
    """Test loops that should not trigger a warning."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration")

    with assert_no_messages(linter):
        walk_checker(linter, executor_checker, root_node)


def test_not_integration_module_ignored(
    linter: UnittestLinter,
    executor_checker: SequentialExecutorJobsChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    await hass.async_add_executor_job(call_a)
    await hass.async_add_executor_job(call_b)
""",
        "tests.components.test_integration",
    )

    with assert_no_messages(linter):
        walk_checker(linter, executor_checker, root_node)
