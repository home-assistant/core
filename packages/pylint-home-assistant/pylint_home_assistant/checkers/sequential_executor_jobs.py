"""Checker for sequential executor job calls.

Multiple sequential ``await hass.async_add_executor_job()`` calls should
be grouped into a single executor job to avoid unnecessary context switches
back to the event loop between blocking calls.

https://contributors.home-assistant.io/core/internals/asyncio/#move-blocking-work-to-the-executor
"""

from collections.abc import Collection, Iterator
import re

from astroid import nodes
from astroid.const import Context
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

_DEFAULT_EXECUTOR = "default"

_EXECUTOR_JOB_STATEMENTS = (
    nodes.Assign,
    nodes.AnnAssign,
    nodes.AugAssign,
    nodes.Expr,
    nodes.Return,
)

# Statements that do not yield to the event loop when they contain no await
_TRANSPARENT_STATEMENTS = (
    nodes.Assign,
    nodes.AnnAssign,
    nodes.AugAssign,
    nodes.Expr,
    nodes.Assert,
    nodes.Delete,
    nodes.Pass,
)

_LOOP_ONLY_FUNCTIONS = frozenset(
    {
        "all_tasks",
        "call_at",
        "call_later",
        "call_soon",
        "create_future",
        "create_task",
        "current_task",
        "ensure_future",
        "get_event_loop",
        "get_running_loop",
        "timeout",
    }
)

_NEW_SCOPE_NODES = (
    nodes.FunctionDef,
    nodes.AsyncFunctionDef,
    nodes.Lambda,
    nodes.ClassDef,
)


def _is_hass_receiver(node: nodes.NodeNG) -> bool:
    """Return True if *node* is ``hass``, ``self.hass`` or ``self._hass``."""
    if isinstance(node, nodes.Name):
        return bool(node.name == "hass")
    return isinstance(node, nodes.Attribute) and node.attrname in {"hass", "_hass"}


def _executor_key(call: nodes.Call) -> str | None:
    """Return the executor *call* submits work to, or None if not an executor job.

    Jobs submitted to different executors must not be grouped, so the
    returned key identifies the executor.
    """
    func = call.func
    if isinstance(func, nodes.Name):
        return _DEFAULT_EXECUTOR if func.name == "to_thread" else None
    if not isinstance(func, nodes.Attribute):
        return None
    if func.attrname == "async_add_executor_job":
        if _is_hass_receiver(func.expr):
            return _DEFAULT_EXECUTOR
        return str(func.expr.as_string())
    if func.attrname == "async_add_import_executor_job":
        return f"import:{func.expr.as_string()}"
    if func.attrname == "run_in_executor":
        if not call.args:
            return None
        executor = call.args[0]
        if isinstance(executor, nodes.Const) and executor.value is None:
            return _DEFAULT_EXECUTOR
        return str(executor.as_string())
    if (
        func.attrname == "to_thread"
        and isinstance(func.expr, nodes.Name)
        and func.expr.name == "asyncio"
    ):
        return _DEFAULT_EXECUTOR
    return None


def _eager_nodes(
    node: nodes.NodeNG, generator_bodies: bool = False
) -> Iterator[nodes.NodeNG]:
    """Yield *node* and its descendants that run when *node* is evaluated.

    With *generator_bodies*, the bodies of generator expressions are included.
    """
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, nodes.GeneratorExp) and not generator_bodies:
            # The body of a generator expression runs only when it is consumed
            stack.append(current.generators[0].iter)
            continue
        if isinstance(current, _NEW_SCOPE_NODES) and not isinstance(
            current, nodes.ClassDef
        ):
            # Only the decorators and default values run at definition time
            stack.extend(
                child
                for child in (
                    getattr(current, "decorators", None),
                    getattr(current, "args", None),
                )
                if child is not None
            )
            continue
        stack.extend(current.get_children())


def _awaits(node: nodes.NodeNG) -> list[nodes.Await]:
    """Return the awaits in *node* that run when *node* is evaluated."""
    return [child for child in _eager_nodes(node) if isinstance(child, nodes.Await)]


def _suspends_implicitly(node: nodes.NodeNG) -> bool:
    """Return True if *node* suspends without an explicit await.

    Async comprehensions await on each iteration, and a yield suspends until
    the consumer resumes the generator.
    """
    return any(
        isinstance(child, (nodes.Yield, nodes.YieldFrom))
        or (isinstance(child, nodes.Comprehension) and child.is_async)
        for child in _eager_nodes(node)
    )


def _executor_job_key(node: nodes.NodeNG) -> str | None:
    """Return the executor key if *node* only awaits a single executor job."""
    if not isinstance(node, _EXECUTOR_JOB_STATEMENTS):
        return None
    awaits = _awaits(node)
    if len(awaits) != 1 or not isinstance(call := awaits[0].value, nodes.Call):
        return None
    # The rest of the statement runs in the event loop between this job and
    # its neighbors, so it must not use loop-only APIs or suspend.
    if _suspends_implicitly(node) or _calls_loop_only_api(node, exclude=(call,)):
        return None
    return _executor_key(call)


def _calls_loop_only_api(
    node: nodes.NodeNG, exclude: Collection[nodes.Call] = ()
) -> bool:
    """Return True if *node* calls a function that must run in the event loop.

    This covers functions named ``async_*`` and the asyncio loop APIs. Such
    calls cannot be moved into an executor job together with the surrounding
    blocking calls.
    """
    # Generator expression bodies are included, as sync code often consumes
    # them right away.
    for call in _eager_nodes(node, generator_bodies=True):
        if not isinstance(call, nodes.Call) or call in exclude:
            continue
        func = call.func
        name = func.attrname if isinstance(func, nodes.Attribute) else None
        if isinstance(func, nodes.Name):
            name = func.name
        if name is not None and (
            name.lstrip("_").startswith("async_") or name in _LOOP_ONLY_FUNCTIONS
        ):
            return True
    return False


def _is_transparent(node: nodes.NodeNG) -> bool:
    """Return True if *node* can move into an executor job with its neighbors."""
    return (
        isinstance(node, _TRANSPARENT_STATEMENTS)
        and not _awaits(node)
        and not _suspends_implicitly(node)
        and not _calls_loop_only_api(node)
    )


def _loop_executor_key(loop: nodes.For | nodes.While) -> str | None:
    """Return the executor key if every await in *loop* is a job on that executor.

    Such a loop can move into a single executor job. Loops that suspend in any
    other way, return or call loop-only APIs must stay in the event loop.
    """
    parts: list[nodes.NodeNG] = list(loop.body)
    if isinstance(loop, nodes.While):
        parts.append(loop.test)
    keys: set[str] = set()
    jobs: list[nodes.Call] = []
    for part in parts:
        for child in _eager_nodes(part):
            if isinstance(
                child,
                (
                    nodes.AsyncFor,
                    nodes.AsyncWith,
                    nodes.Return,
                    nodes.Yield,
                    nodes.YieldFrom,
                ),
            ) or (isinstance(child, nodes.Comprehension) and child.is_async):
                return None
            if not isinstance(child, nodes.Await):
                continue
            if (
                not isinstance(call := child.value, nodes.Call)
                or (key := _executor_key(call)) is None
            ):
                return None
            keys.add(key)
            jobs.append(call)
    if len(keys) != 1 or any(_calls_loop_only_api(part, jobs) for part in parts):
        return None
    key = keys.pop()
    # Each iteration can use a different executor when the loop rebinds it
    if _rebinds_executor(loop, key):
        return None
    return key


def _in_executor_loop(node: nodes.NodeNG) -> bool:
    """Return True if an enclosing loop of *node* can move into an executor job."""
    parent = node.parent
    while parent is not None and not isinstance(parent, _NEW_SCOPE_NODES):
        if isinstance(parent, (nodes.For, nodes.While)) and _loop_executor_key(parent):
            return True
        parent = parent.parent
    return False


def _rebinds_executor(node: nodes.NodeNG, executor: str) -> bool:
    """Return True if *node* may change which executor *executor* refers to."""
    if executor == _DEFAULT_EXECUTOR:
        return False
    expression = executor.removeprefix("import:")
    for target in node.nodes_of_class(
        (
            nodes.AssignName,
            nodes.DelName,
            nodes.AssignAttr,
            nodes.DelAttr,
            nodes.Subscript,
        ),
        skip_klass=_NEW_SCOPE_NODES,
    ):
        if isinstance(target, (nodes.AssignName, nodes.DelName)):
            name = target.name
        elif isinstance(target, nodes.Subscript):
            if target.ctx == Context.Load:
                continue
            name = target.value.as_string()
        else:
            name = f"{target.expr.as_string()}.{target.attrname}"
        # Any name the expression refers to, such as a subscript index or a
        # call argument, can change the executor it evaluates to.
        if re.search(rf"(?<![\w.]){re.escape(name)}(?!\w)", expression):
            return True
    return False


class SequentialExecutorJobsChecker(BaseChecker):
    """Checker for sequential executor job calls."""

    name = "home_assistant_sequential_executor_jobs"
    priority = -1
    msgs = {
        "W7415": (
            "Sequential `async_add_executor_job` calls should be grouped "
            "into a single executor job",
            "home-assistant-sequential-executor-jobs",
            "Used when multiple awaited executor jobs (such as "
            "hass.async_add_executor_job()) run in sequence without yielding "
            "to the event loop in between. Group the blocking operations into "
            "a single function and call async_add_executor_job once.",
        ),
        "W7444": (
            "Executor job inside a loop should be moved into a single executor job",
            "home-assistant-executor-job-in-loop",
            "Used when a loop only awaits executor jobs on the same executor. "
            "Every iteration switches back to the event loop. Move the loop "
            "into a single function and call async_add_executor_job once.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check for sequential executor job calls."""
        if not self._in_integration:
            return

        self._check_body(node.body)

    visit_asyncfunctiondef = visit_functiondef

    def _check_body(self, body: list[nodes.NodeNG]) -> None:
        """Check a list of statements for sequential executor job calls."""
        prev_executor: str | None = None

        for stmt in body:
            if (executor := _executor_job_key(stmt)) is not None:
                if executor == prev_executor:
                    self.add_message(
                        "home-assistant-sequential-executor-jobs",
                        node=stmt,
                    )
                prev_executor = None if _rebinds_executor(stmt, executor) else executor
                continue

            if not _is_transparent(stmt) or (
                prev_executor is not None and _rebinds_executor(stmt, prev_executor)
            ):
                prev_executor = None

            # Recurse into control flow blocks (but not nested functions)
            if isinstance(stmt, nodes.If):
                self._check_body(stmt.body)
                self._check_body(stmt.orelse)
            elif isinstance(stmt, (nodes.Try, nodes.TryStar)):
                self._check_body(stmt.body)
                for handler in stmt.handlers:
                    self._check_body(handler.body)
                self._check_body(stmt.orelse)
                self._check_body(stmt.finalbody)
            elif isinstance(stmt, (nodes.With, nodes.AsyncWith)):
                self._check_body(stmt.body)
            elif isinstance(stmt, (nodes.For, nodes.AsyncFor, nodes.While)):
                if (
                    not isinstance(stmt, nodes.AsyncFor)
                    and _loop_executor_key(stmt) is not None
                    and not _in_executor_loop(stmt)
                ):
                    self.add_message("home-assistant-executor-job-in-loop", node=stmt)
                self._check_body(stmt.body)
                self._check_body(stmt.orelse)
            elif isinstance(stmt, nodes.Match):
                for case in stmt.cases:
                    self._check_body(case.body)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SequentialExecutorJobsChecker(linter))
