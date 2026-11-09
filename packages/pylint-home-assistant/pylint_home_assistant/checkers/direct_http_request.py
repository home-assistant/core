"""Checker that flags HTTP requests made directly from integration code.

Integrations must not talk to a device or service over HTTP themselves. All
API-specific code belongs in a third-party library published on PyPI, which
the integration then uses. This keeps the integration focused on Home
Assistant concepts and lets the library be tested, reused and released on its
own.

The checker flags HTTP requests made with ``requests``, ``aiohttp`` and
``httpx``/``httpx2`` from modules under ``homeassistant.components``:

- module level request functions, such as ``requests.get(...)``,
  ``aiohttp.request(...)`` and ``httpx2.post(...)``;
- request methods (``get``, ``post``, ``request``, ``ws_connect``, ...) called
  on a session or client, such as the result of ``async_get_clientsession``,
  ``get_async_client``, ``aiohttp.ClientSession()`` or ``requests.Session()``,
  or an argument or attribute annotated with one of those types.

Importing these packages is fine: catching their exceptions, or creating a
session to pass to a library, does not make a request. Integrations which are
allowed to make requests are listed in ``_ALLOWED_INTEGRATIONS``.

https://developers.home-assistant.io/docs/api_lib_index
"""

from astroid import bases, nodes
from pylint.checkers import BaseChecker
from pylint.checkers.utils import node_frame_class, safe_infer
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module

_MESSAGE = "home-assistant-direct-http-request"

# Integrations which are allowed to make HTTP requests directly:
# - integrations whose purpose is making generic HTTP requests;
# - entity base components, which fetch URLs provided by their entities;
# - Home Assistant's own infrastructure.
# Do not add integrations which talk to a specific device or service. Existing
# requests of those disable the message on the line instead, so new ones are
# still flagged.
_ALLOWED_INTEGRATIONS = frozenset(
    {
        # Generic HTTP requests
        "downloader",
        "generic",
        "mjpeg",
        "rest",
        "rest_command",
        "scrape",
        # Entity base components
        "image",
        "media_player",
        # Home Assistant infrastructure
        "analytics",
        "auth",
        "blueprint",
        "brands",
        "frontend",
        "homeassistant_alerts",
        "marketplace",
        "system_health",
    }
)

_HTTP_LIBRARIES = ("aiohttp", "httpx", "httpx2", "requests")

_REQUEST_METHODS = frozenset(
    {
        "delete",
        "get",
        "head",
        "options",
        "patch",
        "post",
        "put",
        "request",
        "send",
        "stream",
        "ws_connect",
    }
)

# Module level functions which make a request when called.
_REQUEST_FUNCTIONS = frozenset(
    {
        "aiohttp.request",
        "aiohttp.client.request",
        *(
            f"{module}.{method}"
            for module in ("httpx", "httpx2", "requests", "requests.api")
            for method in (
                "delete",
                "get",
                "head",
                "options",
                "patch",
                "post",
                "put",
                "request",
            )
        ),
        "httpx.stream",
        "httpx2.stream",
    }
)

# Session and client classes on which request methods are flagged.
_SESSION_TYPES = frozenset(
    {
        "aiohttp.ClientSession",
        "aiohttp.client.ClientSession",
        "httpx.AsyncClient",
        "httpx.Client",
        "httpx2.AsyncClient",
        "httpx2.Client",
        "requests.Session",
        "requests.session",
        "requests.sessions.Session",
        "requests.sessions.session",
    }
)

# Functions which return a session or client.
_SESSION_FACTORIES = frozenset(
    {
        *_SESSION_TYPES,
        "homeassistant.helpers.aiohttp_client.async_create_clientsession",
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        "homeassistant.helpers.httpx_client.create_async_httpx_client",
        "homeassistant.helpers.httpx_client.get_async_client",
    }
)

# Class names used to recognise sessions found through inference.
_SESSION_CLASS_NAMES = frozenset({"AsyncClient", "Client", "ClientSession", "Session"})

# Limit how far assignments are followed, to avoid cycles.
_MAX_DEPTH = 5


def _resolve_name(node: nodes.NodeNG) -> str | None:
    """Return the fully qualified name *node* refers to, based on imports.

    Only absolute imports are resolved. ``requests.get`` after
    ``import requests`` and ``get`` after ``from requests import get`` both
    resolve to ``requests.get``.
    """
    if isinstance(node, nodes.Attribute):
        if (parent := _resolve_name(node.expr)) is None:
            return None
        return f"{parent}.{node.attrname}"
    if not isinstance(node, nodes.Name):
        return None
    _, assignments = node.lookup(node.name)
    for assignment in assignments:
        if isinstance(assignment, nodes.Import):
            module: str
            for module, alias in assignment.names:
                if alias == node.name:
                    return module
                if alias is None and (root := module.partition(".")[0]) == node.name:
                    return root
        elif isinstance(assignment, nodes.ImportFrom):
            if assignment.level:
                return None
            for name, alias in assignment.names:
                if (alias or name) == node.name:
                    return f"{assignment.modname}.{name}"
    return None


def _is_session_annotation(annotation: nodes.NodeNG | None) -> bool:
    """Return True if *annotation* is a session type, optionally ``| None``."""
    if annotation is None:
        return False
    if isinstance(annotation, nodes.BinOp):
        return _is_session_annotation(annotation.left) or _is_session_annotation(
            annotation.right
        )
    return _resolve_name(annotation) in _SESSION_TYPES


def _argument_annotation(arguments: nodes.Arguments, name: str) -> nodes.NodeNG | None:
    """Return the annotation of the argument called *name*."""
    for args, annotations in (
        (arguments.posonlyargs, arguments.posonlyargs_annotations),
        (arguments.args or [], arguments.annotations),
        (arguments.kwonlyargs, arguments.kwonlyargs_annotations),
    ):
        for arg, annotation in zip(args, annotations, strict=False):
            if arg.name == name:
                return annotation
    return None


def _is_session_assign_target(target: nodes.NodeNG, depth: int) -> bool:
    """Return True if the assignment target *target* holds a session."""
    parent = target.parent
    if isinstance(parent, nodes.Arguments):
        return _is_session_annotation(_argument_annotation(parent, target.name))
    if isinstance(parent, nodes.AnnAssign):
        return _is_session_annotation(parent.annotation) or (
            parent.value is not None and _is_session_expr(parent.value, depth + 1)
        )
    if isinstance(parent, (nodes.Assign, nodes.NamedExpr)):
        return _is_session_expr(parent.value, depth + 1)
    if isinstance(parent, (nodes.With, nodes.AsyncWith)):
        return any(
            alias is target and _is_session_expr(expr, depth + 1)
            for expr, alias in parent.items
        )
    return False


def _with_item_targets(node: nodes.Name) -> list[nodes.AssignName]:
    """Return targets named like *node* bound earlier in the same ``with``.

    astroid does not find names bound by an earlier item of the ``with``
    statement *node* is part of, as in
    ``async with ClientSession() as session, session.get(url) as resp``.
    """
    for parent in node.node_ancestors():
        if isinstance(parent, (nodes.With, nodes.AsyncWith)):
            return [
                alias
                for _, alias in parent.items
                if isinstance(alias, nodes.AssignName) and alias.name == node.name
            ]
        if parent.is_statement:
            break
    return []


def _is_session_attribute(node: nodes.Attribute, depth: int) -> bool:
    """Return True if ``self.<attr>`` holds a session."""
    if not (isinstance(node.expr, nodes.Name) and node.expr.name == "self"):
        return False
    if (klass := node_frame_class(node)) is None:
        return False
    # Class level annotation, e.g. ``session: ClientSession`` on a dataclass.
    for local in klass.locals.get(node.attrname, []):
        if _is_session_assign_target(local, depth):
            return True
    # Assignments to ``self.<attr>`` in any method.
    return any(
        _is_session_assign_target(assign_attr, depth)
        for assign_attr in klass.instance_attrs.get(node.attrname, [])
    )


def _is_session_inferred(node: nodes.NodeNG) -> bool:
    """Return True if astroid infers *node* to be a session instance."""
    if not isinstance(value := safe_infer(node), bases.Instance):
        return False
    module, _, class_name = value.pytype().rpartition(".")
    return (
        class_name in _SESSION_CLASS_NAMES and module.split(".")[0] in _HTTP_LIBRARIES
    )


def _is_session_expr(node: nodes.NodeNG, depth: int = 0) -> bool:
    """Return True if *node* evaluates to an HTTP session or client."""
    if depth > _MAX_DEPTH:
        return False
    if isinstance(node, nodes.Await):
        return _is_session_expr(node.value, depth + 1)
    if isinstance(node, nodes.Call):
        return _resolve_name(node.func) in _SESSION_FACTORIES
    if isinstance(node, nodes.Name):
        _, assignments = node.lookup(node.name)
        if not assignments:
            assignments = _with_item_targets(node)
        return any(
            isinstance(assignment, nodes.AssignName)
            and _is_session_assign_target(assignment, depth)
            for assignment in assignments
        )
    if isinstance(node, nodes.Attribute) and _is_session_attribute(node, depth):
        return True
    return depth == 0 and _is_session_inferred(node)


class HassDirectHttpRequestChecker(BaseChecker):
    """Checker for HTTP requests made directly from integration code."""

    name = "home_assistant_direct_http_request"
    priority = -1
    msgs = {
        "W7464": (
            "Integrations should not make HTTP requests directly (`%s`); move "
            "the API communication into a library published on PyPI",
            _MESSAGE,
            "Used when an integration makes an HTTP request with requests, "
            "aiohttp or httpx itself. All API-specific code has to be part of "
            "a third-party library published on PyPI. See "
            "https://developers.home-assistant.io/docs/api_lib_index",
        ),
    }
    options = ()

    _enabled: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Check whether the module belongs to an integration."""
        integration = parse_module(node.name)
        self._enabled = (
            integration is not None and integration.domain not in _ALLOWED_INTEGRATIONS
        )

    def visit_call(self, node: nodes.Call) -> None:
        """Flag calls which make an HTTP request."""
        if not self._enabled:
            return

        func = node.func
        if (name := _resolve_name(func)) in _REQUEST_FUNCTIONS:
            self.add_message(_MESSAGE, node=node, args=(name,))
            return

        if (
            isinstance(func, nodes.Attribute)
            and func.attrname in _REQUEST_METHODS
            and _is_session_expr(func.expr)
        ):
            self.add_message(_MESSAGE, node=node, args=(func.as_string(),))


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassDirectHttpRequestChecker(linter))
