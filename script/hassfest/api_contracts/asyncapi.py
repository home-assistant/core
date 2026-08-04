"""Generate the Home Assistant Core WebSocket and SSE AsyncAPI contract."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from .common import (
    IntegrationMetadata,
    Interface,
    SourceIndex,
    decorator_name,
    interface_metadata,
    slug,
    source_description,
)
from .schema import annotation_schema, mapping_key, mapping_schema, schema_mapping


@dataclass(frozen=True, slots=True)
class Command(Interface):
    """WebSocket command discovered from a websocket_command decorator."""

    payload: dict[str, Any]
    result: dict[str, Any] | None
    requires_admin: bool
    documentation: str

    def render(self) -> dict[str, Any]:
        """Render this command as an AsyncAPI message."""
        message: dict[str, Any] = {
            "name": self.name,
            "payload": self.payload,
            "externalDocs": {"url": self.documentation},
        }
        if self.summary:
            message["summary"] = self.summary
        if self.description:
            message["description"] = self.description
        if self.integration != "websocket_api":
            message["x-home-assistant-requires-integration"] = self.integration
        if self.requires_admin:
            message["x-home-assistant-requires-admin"] = True
        return message

    def render_result(self) -> dict[str, Any]:
        """Render the correlated result for this command."""
        message: dict[str, Any] = {
            "name": f"{self.name} result",
            "title": f"{self.name} result",
            "externalDocs": {"url": self.documentation},
            "payload": {
                "type": "object",
                "required": ["id", "type", "success", "result"],
                "properties": {
                    "id": {"type": "integer"},
                    "type": {"type": "string", "const": "result"},
                    "success": {"type": "boolean", "const": True},
                    "result": self.result,
                },
            },
        }
        return message


def _documentation(integration: str, metadata: IntegrationMetadata) -> str:
    """Return the maintained guide for a WebSocket integration."""
    if integration == "websocket_api":
        return "https://developers.home-assistant.io/docs/api/websocket/"
    return metadata.documentation


def _command_payload(
    index: SourceIndex, module: str, schema: ast.expr, command: str
) -> dict[str, Any]:
    """Render the exact command envelope and directly declared primitive fields."""
    properties: dict[str, Any] = {
        "id": {
            "type": "integer",
            "minimum": 1,
            "description": "Identifier used to correlate the command with responses and events.",
        },
        "type": {"type": "string", "const": command},
    }
    required = ["id", "type"]
    additional_properties: bool | dict[str, Any] = False

    if mapping := schema_mapping(index, module, schema):
        declared = mapping_schema(index, *mapping)
        additional_properties = declared["additionalProperties"]
        properties.update(
            (name, value)
            for name, value in declared["properties"].items()
            if name != "type"
        )
        required.extend(name for name in declared.get("required", []) if name != "type")

    return {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": additional_properties,
    }


def _command_type(index: SourceIndex, module: str, schema: ast.expr) -> str | None:
    """Read the type discriminator from a command schema."""
    if not (mapping := schema_mapping(index, module, schema)):
        return None
    schema_module, node, _ = mapping

    # Only literal discriminators are safe to publish without executing validators.
    for raw_key, value in zip(node.keys, node.values, strict=True):
        if raw_key is None or not (key := mapping_key(index, schema_module, raw_key)):
            continue
        if key[0] == "type" and isinstance(
            command := index.value(schema_module, value), str
        ):
            return command
    return None


def _commands(
    index: SourceIndex, integrations: dict[str, IntegrationMetadata]
) -> list[Command]:
    commands: dict[str, Command] = {}
    for module, tree in sorted(index.trees.items()):
        if not module.startswith("homeassistant.components."):
            continue

        integration = module.split(".")[2]
        if integration not in integrations:
            continue

        for handler in (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            for decorator in handler.decorator_list:
                if (
                    not isinstance(decorator, ast.Call)
                    or decorator_name(decorator) != "websocket_command"
                    or not decorator.args
                    or not (command := _command_type(index, module, decorator.args[0]))
                ):
                    continue

                summary, description = interface_metadata(index, module, handler)
                commands[command] = Command(
                    name=command,
                    integration=integration,
                    summary=summary,
                    description=description,
                    payload=_command_payload(index, module, decorator.args[0], command),
                    result=next(
                        (
                            annotation_schema(index, module, keyword.value)
                            for keyword in decorator.keywords
                            if keyword.arg == "result"
                        ),
                        None,
                    ),
                    requires_admin=any(
                        decorator_name(item) == "require_admin"
                        for item in handler.decorator_list
                    ),
                    documentation=_documentation(
                        integration, integrations[integration]
                    ),
                )
    return [commands[name] for name in sorted(commands)]


def _protocol_messages(
    index: SourceIndex,
    documentation: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Return WebSocket messages that are not registered commands."""

    def status(name: str, *, message: bool = False) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "type": {"type": "string", "const": name},
            "ha_version": {"type": "string"},
        }
        required = ["type"]
        if message:
            properties["message"] = {"type": "string"}
            required.append("message")
        else:
            required.append("ha_version")
        return {
            "name": name,
            "externalDocs": documentation,
            "payload": {
                "type": "object",
                "required": required,
                "properties": properties,
            },
        }

    error_schema = {
        "type": "object",
        "description": source_description(
            index,
            "homeassistant.exceptions",
            index.classes[("homeassistant.exceptions", "ServiceValidationError")],
            "Errors may include localized details from Home Assistant exceptions.",
        ),
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
            "translation_domain": {"type": "string"},
            "translation_key": {"type": "string"},
            "translation_placeholders": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
    }

    # These frames belong to the protocol itself, so no command decorator exposes them.
    messages: dict[str, dict[str, Any]] = {
        "auth": {
            "name": "auth",
            "title": "Authenticate the WebSocket connection",
            "externalDocs": documentation,
            "payload": {
                "type": "object",
                "required": ["type", "access_token"],
                "properties": {
                    "type": {"type": "string", "const": "auth"},
                    "access_token": {"type": "string", "writeOnly": True},
                },
            },
        },
        "auth_required": status("auth_required"),
        "auth_ok": status("auth_ok"),
        "auth_invalid": status("auth_invalid", message=True),
        "result": {
            "name": "result",
            "title": "Command result",
            "externalDocs": documentation,
            "payload": {
                "type": "object",
                "required": ["id", "type", "success"],
                "properties": {
                    "id": {"type": "integer"},
                    "type": {"type": "string", "const": "result"},
                    "success": {"type": "boolean"},
                    "result": {},
                    "error": error_schema,
                },
            },
        },
        "result_error": {
            "name": "result error",
            "title": "Command error",
            "externalDocs": documentation,
            "payload": {
                "type": "object",
                "required": ["id", "type", "success", "error"],
                "properties": {
                    "id": {"type": "integer"},
                    "type": {"type": "string", "const": "result"},
                    "success": {"type": "boolean", "const": False},
                    "error": error_schema,
                },
            },
        },
        "event": {
            "name": "event",
            "title": "Subscription event",
            "externalDocs": documentation,
            "payload": {
                "type": "object",
                "required": ["id", "type", "event"],
                "properties": {
                    "id": {"type": "integer"},
                    "type": {"type": "string", "const": "event"},
                    "event": {},
                },
            },
        },
        "pong": {
            "name": "pong",
            "title": "Ping response",
            "externalDocs": documentation,
            "payload": {
                "type": "object",
                "required": ["id", "type"],
                "properties": {
                    "id": {"type": "integer"},
                    "type": {"type": "string", "const": "pong"},
                },
            },
        },
        "sse_event": {
            "name": "sse_event",
            "title": "Server-Sent Event",
            "externalDocs": documentation,
            "payload": {"type": "string"},
            "contentType": "text/event-stream",
        },
    }
    return messages


def generate_websocket_asyncapi(
    index: SourceIndex,
    integrations: dict[str, IntegrationMetadata],
) -> dict[str, Any]:
    """Generate an AsyncAPI contract from websocket_command decorators."""
    commands = _commands(index, integrations)
    websocket_docs = {"url": "https://developers.home-assistant.io/docs/api/websocket/"}
    command_messages = {slug(command.name): command.render() for command in commands}
    result_messages = {
        f"{slug(command.name)}_result": command.render_result()
        for command in commands
        if command.result is not None
    }
    # A channel's messages must be exclusive, so each typed result gets a reply channel.
    reply_channels = {
        f"{slug(command.name)}_reply": {
            "address": "/api/websocket",
            "servers": [
                {"$ref": "#/servers/websocket"},
                {"$ref": "#/servers/secure_websocket"},
            ],
            "messages": {
                f"{slug(command.name)}_result": {
                    "$ref": f"#/components/messages/{slug(command.name)}_result"
                },
                "result_error": {"$ref": "#/components/messages/result_error"},
            },
        }
        for command in commands
        if command.result is not None
    }
    protocol_messages = _protocol_messages(index, websocket_docs)
    messages = {**command_messages, **result_messages, **protocol_messages}
    return {
        "asyncapi": "3.1.0",
        "defaultContentType": "application/json",
        "info": {
            "title": "Home Assistant Core streaming APIs",
            "version": "1",
            "description": "WebSocket commands and the Server-Sent Events stream provided by Home Assistant Core.",
        },
        "servers": {
            "websocket": {
                "host": "{host}",
                "protocol": "ws",
                "variables": {"host": {"default": "homeassistant.local:8123"}},
            },
            "secure_websocket": {
                "host": "{host}",
                "protocol": "wss",
                "variables": {"host": {"default": "homeassistant.local:8123"}},
            },
            "http": {
                "host": "{host}",
                "protocol": "http",
                "security": [{"$ref": "#/components/securitySchemes/bearerAuth"}],
                "variables": {"host": {"default": "homeassistant.local:8123"}},
            },
            "https": {
                "host": "{host}",
                "protocol": "https",
                "security": [{"$ref": "#/components/securitySchemes/bearerAuth"}],
                "variables": {"host": {"default": "homeassistant.local:8123"}},
            },
        },
        "channels": {
            "websocket": {
                "address": "/api/websocket",
                "description": "Authenticated command and event channel.",
                "servers": [
                    {"$ref": "#/servers/websocket"},
                    {"$ref": "#/servers/secure_websocket"},
                ],
                "messages": {
                    key: {"$ref": f"#/components/messages/{key}"}
                    for key in command_messages.keys()
                    | (protocol_messages.keys() - {"sse_event", "result_error"})
                },
            },
            "event_stream": {
                "address": "/api/stream",
                "description": "Authenticated Server-Sent Events stream.",
                "servers": [
                    {"$ref": "#/servers/http"},
                    {"$ref": "#/servers/https"},
                ],
                "messages": {"event": {"$ref": "#/components/messages/sse_event"}},
            },
            **reply_channels,
        },
        # AsyncAPI actions are from the server's perspective. A received command may
        # link to its typed result; commands without one use the generic result frame.
        "operations": {
            "receive_authentication": {
                "action": "receive",
                "title": "authentication",
                "channel": {"$ref": "#/channels/websocket"},
                "messages": [{"$ref": "#/channels/websocket/messages/auth"}],
            },
            "send_authentication_status": {
                "action": "send",
                "title": "authentication status",
                "channel": {"$ref": "#/channels/websocket"},
                "messages": [
                    {"$ref": "#/channels/websocket/messages/auth_required"},
                    {"$ref": "#/channels/websocket/messages/auth_ok"},
                    {"$ref": "#/channels/websocket/messages/auth_invalid"},
                ],
            },
            **{
                f"receive_{slug(command.name)}": {
                    "action": "receive",
                    "title": command.name,
                    "channel": {"$ref": "#/channels/websocket"},
                    "tags": [
                        {
                            "name": command.integration,
                            "description": integrations[
                                command.integration
                            ].description,
                            "externalDocs": {
                                "url": _documentation(
                                    command.integration,
                                    integrations[command.integration],
                                )
                            },
                        }
                    ],
                    "messages": [
                        {"$ref": f"#/channels/websocket/messages/{slug(command.name)}"}
                    ],
                    "reply": {
                        "channel": {
                            "$ref": (
                                f"#/channels/{slug(command.name)}_reply"
                                if command.result is not None
                                else "#/channels/websocket"
                            )
                        },
                        "messages": [
                            {
                                "$ref": (
                                    f"#/channels/{slug(command.name)}_reply/messages/{slug(command.name)}_result"
                                    if command.result is not None
                                    else "#/channels/websocket/messages/result"
                                )
                            },
                            *(
                                [
                                    {
                                        "$ref": f"#/channels/{slug(command.name)}_reply/messages/result_error"
                                    }
                                ]
                                if command.result is not None
                                else []
                            ),
                        ],
                    },
                }
                for command in commands
            },
            "send_websocket": {
                "action": "send",
                "title": "results and events",
                "channel": {"$ref": "#/channels/websocket"},
                "messages": [
                    {"$ref": "#/channels/websocket/messages/result"},
                    {"$ref": "#/channels/websocket/messages/event"},
                    {"$ref": "#/channels/websocket/messages/pong"},
                ],
            },
            "send_event_stream": {
                "action": "send",
                "title": "server-sent events",
                "x-home-assistant-requires-admin": True,
                "channel": {"$ref": "#/channels/event_stream"},
                "messages": [{"$ref": "#/channels/event_stream/messages/event"}],
            },
        },
        "components": {
            "messages": messages,
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
        },
    }
