"""Generate the Home Assistant Core HTTP OpenAPI contract."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from http import HTTPMethod
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
    source_description,
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
    requires_admin: bool
    documentation: str
    request: dict[str, Any] | None
    request_required: bool
    response: dict[str, Any] | None

    def render(self, operation_id: str) -> dict[str, Any]:
        """Render this endpoint as an OpenAPI operation."""
        operation: dict[str, Any] = {
            "operationId": operation_id,
            "tags": [self.integration],
            "responses": {
                "200": {"$ref": "#/components/responses/Success"},
                "400": {"$ref": "#/components/responses/BadRequest"},
            },
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
            operation["security"] = [{name: []} for name in self.security]
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

        if self.response:
            operation["responses"]["200"] = {
                "description": "Successful response",
                "content": {"application/json": {"schema": self.response}},
            }

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

    def handlers(self) -> dict[str, Handler]:
        """Resolve inherited HTTP handlers and local method aliases."""
        handlers: dict[str, Handler] = {}
        # Mirror Python lookup order: earlier bases win, then the subclass wins.
        for base in reversed(self.bases()):
            handlers.update(base.handlers())

        local = {
            node.name: node
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

        name = view.value("name")
        if not isinstance(name, str):
            name = class_name
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
            for method, handler in view.handlers().items():
                # Optional integrations can register competing routes.
                if (path, method) in seen:
                    continue
                seen.add((path, method))

                summary, description = interface_metadata(
                    index, module, handler, class_node
                )
                request: dict[str, Any] | None = None
                request_required = False
                response: dict[str, Any] | None = None

                for decorator in handler.decorator_list:
                    if (
                        not isinstance(decorator, ast.Call)
                        or decorator_name(decorator) != "RequestDataValidator"
                    ):
                        continue
                    if decorator.args and (
                        mapping := schema_mapping(index, module, decorator.args[0])
                    ):
                        request = mapping_schema(index, *mapping)
                        allow_empty = (
                            index.value(module, decorator.args[1])
                            if len(decorator.args) > 1
                            else next(
                                (
                                    index.value(module, keyword.value)
                                    for keyword in decorator.keywords
                                    if keyword.arg == "allow_empty"
                                ),
                                False,
                            )
                        )
                        request_required = allow_empty is not True
                    response = next(
                        (
                            annotation_schema(index, module, keyword.value)
                            for keyword in decorator.keywords
                            if keyword.arg == "response"
                        ),
                        None,
                    )

                endpoints.append(
                    Endpoint(
                        name=name,
                        integration=integration,
                        summary=summary,
                        description=description,
                        path=path,
                        raw_path=raw_path,
                        method=method,
                        class_name=class_name,
                        requires_auth=requires_auth,
                        security=security,
                        requires_admin=any(
                            decorator_name(item) == "require_admin"
                            for item in handler.decorator_list
                        ),
                        documentation=_documentation(integration, metadata),
                        request=request,
                        request_required=request_required,
                        response=response,
                    )
                )
    return endpoints


def _mobile_app_schemas(index: SourceIndex) -> dict[str, dict[str, Any]]:
    """Generate mobile app webhook payloads from their registered validators."""
    module = "homeassistant.components.mobile_app.webhook"
    schemas: dict[str, dict[str, Any]] = {}

    for (handler_module, _), handler in index.functions.items():
        if handler_module != module:
            continue

        command: str | None = None
        data: dict[str, Any] | None = None

        for decorator in handler.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            if decorator_name(decorator) == "register" and isinstance(
                value := index.value(module, decorator.args[0]), str
            ):
                command = value
            elif decorator_name(decorator) == "validate_schema" and (
                mapping := schema_mapping(index, module, decorator.args[0])
            ):
                data = mapping_schema(index, *mapping)

        if command is None:
            continue

        properties: dict[str, Any] = {"type": {"type": "string", "const": command}}
        required = ["type"]

        if data is not None:
            properties["data"] = data
            required.append("data")

        schemas[f"mobile_app_{slug(command)}"] = {
            "type": "object",
            "description": source_description(
                index, module, handler, ast.get_docstring(handler) or ""
            ),
            "required": required,
            "properties": properties,
        }
    return schemas


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
            "schemas": _mobile_app_schemas(index),
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
