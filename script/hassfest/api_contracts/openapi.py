"""Generate the Home Assistant Core HTTP OpenAPI contract."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from http import HTTPMethod, HTTPStatus
from typing import Any

from .common import (
    PATH_PARAMETER,
    Handler,
    IntegrationMetadata,
    Interface,
    SourceIndex,
    assignments,
    decorator_name,
    interface_metadata,
    slug,
)
from .schema import annotation_schema, mapping_schema, schema_mapping


@dataclass(frozen=True, slots=True)
class Endpoint(Interface):
    """HTTP endpoint discovered from a HomeAssistantView."""

    path: str
    raw_path: str
    method: str
    class_name: str
    requires_auth: bool | None
    security: list[str] | None
    security_optional: bool
    requires_admin: bool
    documentation: str
    request: dict[str, Any] | None
    request_required: bool
    responses: dict[str, dict[str, Any] | None]

    def render(self, operation_id: str) -> dict[str, Any]:
        """Render this endpoint as an OpenAPI operation."""
        operation: dict[str, Any] = {
            "operationId": operation_id,
            "tags": [self.integration],
            "responses": {"400": {"$ref": "#/components/responses/BadRequest"}},
            "externalDocs": {"url": self.documentation},
        }

        if self.summary:
            operation["summary"] = self.summary

        if self.description:
            operation["description"] = self.description

        if parameters := [
            {
                "name": parameter,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
            for parameter in PATH_PARAMETER.findall(self.raw_path)
        ]:
            operation["parameters"] = parameters

        if self.security:
            security_requirements: list[dict[str, list[str]]] = [
                {name: []} for name in self.security
            ]
            if self.security_optional:
                security_requirements.insert(0, {})
            operation["security"] = security_requirements
            operation["responses"]["401"] = {
                "$ref": "#/components/responses/Unauthorized"
            }
        elif self.requires_auth is False:
            operation["security"] = []
        else:
            operation["security"] = [{"bearerAuth": []}]
            operation["responses"]["401"] = {
                "$ref": "#/components/responses/Unauthorized"
            }

        operation["x-home-assistant-integration"] = self.integration
        if self.requires_admin:
            operation["x-home-assistant-requires-admin"] = True
        if self.raw_path != self.path:
            operation["x-home-assistant-aiohttp-path"] = self.raw_path

        if self.request:
            operation["requestBody"] = {
                "required": self.request_required,
                "content": {"application/json": {"schema": self.request}},
            }

        if not self.responses:
            operation["responses"]["200"] = {"$ref": "#/components/responses/Success"}
        for status, schema in self.responses.items():
            response: dict[str, Any] = {"description": HTTPStatus(int(status)).phrase}
            if schema is not None:
                response["content"] = {"application/json": {"schema": schema}}
            operation["responses"][status] = response

        return operation


class View:
    """Resolve inherited metadata and handlers for one source class."""

    def __init__(
        self,
        index: SourceIndex,
        module: str,
        node: ast.ClassDef,
        seen: set[tuple[str, str]] | None = None,
    ) -> None:
        """Initialize a source view."""
        self.index = index
        self.module = module
        self.node = node
        self.seen = set() if seen is None else seen

    def bases(self) -> list[View]:
        """Return indexed base classes."""
        result: list[View] = []
        for base in self.node.bases:
            if not (target := self.index.class_target(self.module, base)):
                continue
            target_module, name = target
            key = (target_module, name)
            if key in self.seen or not (node := self.index.classes.get(key)):
                continue
            result.append(View(self.index, target_module, node, self.seen | {key}))
        return result

    def is_home_assistant_view(self) -> bool:
        """Return whether this class derives from HomeAssistantView."""
        if self.node.name == "HomeAssistantView":
            return True
        return any(base.is_home_assistant_view() for base in self.bases())

    def value(self, name: str) -> Any:
        """Resolve an inherited class value."""
        local = assignments(self.node.body)
        if expression := local.get(name):
            return self.index.value(
                self.module,
                expression,
                local_assignments={
                    (self.module, key): value for key, value in local.items()
                },
            )
        for base in self.bases():
            if (value := base.value(name)) is not None:
                return value
        return None

    def handlers(self) -> dict[str, tuple[str, Handler]]:
        """Resolve inherited HTTP handlers and local method aliases."""
        handlers: dict[str, tuple[str, Handler]] = {}
        # Mirror Python lookup order: earlier bases win, then the subclass wins.
        for base in reversed(self.bases()):
            handlers.update(base.handlers())

        local = {
            node.name: (self.module, node)
            for node in self.node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        handlers.update(
            (method, handler)
            for method, handler in local.items()
            if method.upper() in HTTPMethod.__members__
        )
        for method, target in assignments(self.node.body).items():
            if method.upper() in HTTPMethod.__members__ and isinstance(
                target, ast.Name
            ):
                if handler := local.get(target.id) or handlers.get(target.id):
                    handlers[method] = handler
        return handlers


def _documentation(integration: str, metadata: IntegrationMetadata) -> str:
    """Return the most relevant maintained guide for an HTTP integration."""
    if integration in {"api", "webhook"}:
        return "https://developers.home-assistant.io/docs/api/rest/"
    if integration == "auth":
        return "https://developers.home-assistant.io/docs/auth_api/"
    if integration == "websocket_api":
        return "https://developers.home-assistant.io/docs/api/websocket/"
    return metadata.documentation


def _normalise_path(path: str) -> str:
    """Convert aiohttp parameter expressions to OpenAPI parameters."""
    return PATH_PARAMETER.sub(lambda match: "{" + match.group(1) + "}", path)


def _response_status(index: SourceIndex, module: str, node: ast.expr) -> int | None:
    """Resolve an integer or stdlib HTTPStatus member."""
    if isinstance(status := index.value(module, node), int):
        return status
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and index.imported(module, node.value.id) == ("http", "HTTPStatus")
        and node.attr in HTTPStatus.__members__
    ):
        return HTTPStatus[node.attr]
    return None


def _endpoints(
    index: SourceIndex, integrations: dict[str, IntegrationMetadata]
) -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    seen: set[tuple[str, str]] = set()

    for (module, class_name), class_node in sorted(index.classes.items()):
        if not module.startswith("homeassistant.components."):
            continue

        integration = module.split(".")[2]
        if integration not in integrations or class_name == "WebsocketAPIView":
            continue

        view = View(index, module, class_node)
        if not view.is_home_assistant_view():
            continue
        if not isinstance(url := view.value("url"), str) or not url.startswith("/"):
            continue

        view_name = view.value("name")
        if not isinstance(view_name, str):
            view_name = class_name
        auth = view.value("requires_auth")
        requires_auth = auth if isinstance(auth, bool) else None
        security = view.value("openapi_security")
        if not (
            isinstance(security, list)
            and all(isinstance(item, str) for item in security)
        ):
            security = None
        extra_urls = view.value("extra_urls") or []
        metadata = integrations[integration]

        for raw_path in [url, *extra_urls]:
            if not isinstance(raw_path, str):
                continue
            path = _normalise_path(raw_path)
            for method, (handler_module, handler) in view.handlers().items():
                # Optional integrations can register competing routes.
                if (path, method) in seen:
                    continue
                seen.add((path, method))

                summary, description = interface_metadata(
                    index, handler_module, handler, class_node
                )
                request: dict[str, Any] | None = None
                request_required = False
                responses: dict[str, dict[str, Any] | None] = {}

                for decorator in handler.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue
                    decorator_kind = decorator_name(decorator)
                    if decorator_kind == "api_response" and decorator.args:
                        if (
                            status := _response_status(
                                index, handler_module, decorator.args[0]
                            )
                        ) is not None:
                            responses[str(status)] = (
                                annotation_schema(
                                    index, handler_module, decorator.args[1]
                                )
                                if len(decorator.args) > 1
                                else None
                            )
                        continue
                    if decorator_kind != "RequestDataValidator":
                        continue
                    if decorator.args and (
                        mapping := schema_mapping(
                            index, handler_module, decorator.args[0]
                        )
                    ):
                        request = mapping_schema(index, *mapping)
                        allow_empty = (
                            index.value(handler_module, decorator.args[1])
                            if len(decorator.args) > 1
                            else next(
                                (
                                    index.value(handler_module, keyword.value)
                                    for keyword in decorator.keywords
                                    if keyword.arg == "allow_empty"
                                ),
                                False,
                            )
                        )
                        request_required = allow_empty is not True
                endpoints.append(
                    Endpoint(
                        name=view_name,
                        integration=integration,
                        summary=summary,
                        description=description,
                        path=path,
                        raw_path=raw_path,
                        method=method,
                        class_name=class_name,
                        requires_auth=requires_auth,
                        security=security,
                        security_optional=(
                            view.value("openapi_security_optional") is True
                        ),
                        requires_admin=any(
                            decorator_name(item) == "require_admin"
                            for item in handler.decorator_list
                        ),
                        documentation=_documentation(integration, metadata),
                        request=request,
                        request_required=request_required,
                        responses=responses,
                    )
                )
    return endpoints


def generate_rest_openapi(
    index: SourceIndex,
    integrations: dict[str, IntegrationMetadata],
) -> dict[str, Any]:
    """Generate an OpenAPI contract from HomeAssistantView classes."""
    endpoints = _endpoints(index, integrations)
    paths: dict[str, dict[str, Any]] = {}
    operation_ids: set[str] = set()

    for endpoint in endpoints:
        operation_id = slug(f"{endpoint.name}_{endpoint.method}")
        # View names are not globally unique; integration and class form the fallback.
        if operation_id in operation_ids:
            operation_id = slug(
                f"{endpoint.integration}_{endpoint.class_name}_{endpoint.method}"
            )
            fallback = operation_id
            suffix = 2
            while operation_id in operation_ids:
                operation_id = f"{fallback}_{suffix}"
                suffix += 1
        operation_ids.add(operation_id)
        paths.setdefault(endpoint.path, {})[endpoint.method] = endpoint.render(
            operation_id
        )

    tags = sorted({endpoint.integration for endpoint in endpoints})

    groups = sorted({integrations[tag].group for tag in tags})
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Home Assistant Core HTTP API",
            "version": "1",
            "description": "HTTP interfaces provided by Home Assistant Core and its bundled integrations.",
            "contact": {
                "name": "Home Assistant",
                "url": "https://www.home-assistant.io/",
            },
        },
        "servers": [
            {
                "url": "{scheme}://{host}",
                "variables": {
                    "scheme": {"default": "http", "enum": ["http", "https"]},
                    "host": {"default": "localhost:8123"},
                },
            }
        ],
        "paths": dict(sorted(paths.items())),
        "tags": [
            {
                "name": tag,
                "description": integrations[tag].description,
                "externalDocs": {
                    "url": _documentation(tag, integrations[tag]),
                },
            }
            for tag in tags
        ],
        "x-tagGroups": [
            {
                "name": name,
                "tags": [tag for tag in tags if integrations[tag].group == name],
            }
            for name in groups
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
                "queryToken": {"type": "apiKey", "in": "query", "name": "token"},
            },
            "responses": {
                "Success": {
                    "description": "Successful response",
                },
                "BadRequest": {
                    "description": "Invalid request",
                },
                "Unauthorized": {
                    "description": "Missing or invalid access token",
                    "content": {
                        "text/plain": {
                            "schema": {"type": "string"},
                        }
                    },
                },
            },
        },
    }
