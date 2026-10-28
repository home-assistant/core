"""Generate an AsyncAPI document of the WebSocket API.

Starts Home Assistant from a temporary configuration with the given
integrations and describes every WebSocket command they register.
"""

import argparse
import asyncio
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import inspect
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

import probatio
from probatio.codecs import UNSUPPORTED

from homeassistant.bootstrap import async_setup_hass
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.runner import RuntimeConfig

DEFAULT_INTEGRATIONS = [
    "application_credentials",
    "assist_pipeline",
    "auth",
    "automation",
    "backup",
    "blueprint",
    "calendar",
    "camera",
    "config",
    "conversation",
    "counter",
    "device_automation",
    "diagnostics",
    "energy",
    "frontend",
    "history",
    "homeassistant",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "labs",
    "logbook",
    "logger",
    "lovelace",
    "media_source",
    "person",
    "recorder",
    "repairs",
    "schedule",
    "scene",
    "script",
    "search",
    "system_health",
    "system_log",
    "tag",
    "timer",
    "todo",
    "trace",
    "update",
    "weather",
    "websocket_api",
    "zone",
]

STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING}
ENTITY_ID = {"type": "string", "pattern": r"^[a-z0-9_]+\.[a-z0-9_]+$"}

# Home Assistant validators that probatio can't describe on its own.
VALIDATOR_SCHEMAS: dict[Callable[..., Any], dict[str, Any]] = {
    cv.entity_id: ENTITY_ID,
    cv.strict_entity_id: ENTITY_ID,
    cv.entity_ids: {"type": "array", "items": ENTITY_ID},
    cv.comp_entity_ids: STRINGS,
    cv.entity_id_or_uuid: STRING,
    cv.entity_ids_or_uuids: STRINGS,
    cv.string: STRING,
    cv.slug: {"type": "string", "pattern": r"^[a-z0-9_]+$"},
    cv.url: {"type": "string", "format": "uri"},
    cv.url_no_path: {"type": "string", "format": "uri"},
    cv.datetime: {"type": "string", "format": "date-time"},
    cv.time: {"type": "string", "format": "time"},
    cv.date: {"type": "string", "format": "date"},
    cv.positive_int: {"type": "integer", "minimum": 0},
    cv.positive_float: {"type": "number", "minimum": 0},
    cv.boolean: {"type": "boolean"},
    cv.icon: STRING,
    cv.domain_key: STRING,
    cv.match_all: {},
    cv.template: STRING,
    cv.dynamic_template: STRING,
}

# Validators created by a factory, matched on the qualified name of the inner function.
VALIDATOR_FACTORY_SCHEMAS: dict[str, dict[str, Any]] = {
    "homeassistant.helpers.config_validation.entity_domain.<locals>.validate": ENTITY_ID,
}


class SchemaConverter:
    """Convert command schemas, recording the validators that stay undescribed."""

    def __init__(self) -> None:
        """Initialize the converter."""
        self.unknown: Counter[str] = Counter()

    def _serialize(self, node: Any) -> Any:
        if not callable(node) or isinstance(node, type):
            return UNSUPPORTED
        try:
            if node in VALIDATOR_SCHEMAS:
                return VALIDATOR_SCHEMAS[node]
        except TypeError:
            return UNSUPPORTED
        if inspect.isfunction(node) and node.__module__.startswith("homeassistant"):
            name = f"{node.__module__}.{node.__qualname__}"
            if name in VALIDATOR_FACTORY_SCHEMAS:
                return VALIDATOR_FACTORY_SCHEMAS[name]
            self.unknown[name] += 1
        return UNSUPPORTED

    def convert(self, schema: Any) -> dict[str, Any]:
        """Return the JSON Schema of a command."""
        return probatio.to_json_schema(schema, custom_serializer=self._serialize)


def _open_fields(schema: Any, path: str = "") -> list[str]:
    """Return the paths of fields without any constraint."""
    if isinstance(schema, dict):
        if not schema and path:
            return [path]
        return [
            found
            for key, value in schema.items()
            for found in _open_fields(value, f"{path}/{key}")
        ]
    if isinstance(schema, list):
        return [
            found
            for index, value in enumerate(schema)
            for found in _open_fields(value, f"{path}[{index}]")
        ]
    return []


def _message_id(command: str) -> str:
    return command.replace("/", "_").replace(".", "_")


def _is_subscription(command: str) -> bool:
    """Return if the command sends events after its result."""
    return command.rpartition("/")[2].startswith("subscribe")


def _integration(handler: Callable[..., Any]) -> str:
    module = handler.__module__
    if module.startswith("homeassistant.components."):
        return module.split(".")[2]
    return module


AUTH_MESSAGES: dict[str, dict[str, Any]] = {
    "auth_required": {
        "summary": "Sent by the server right after connecting.",
        "payload": {
            "type": "object",
            "properties": {
                "type": {"const": "auth_required"},
                "ha_version": STRING,
            },
            "required": ["type", "ha_version"],
        },
    },
    "auth": {
        "summary": "Authenticate the connection.",
        "payload": {
            "type": "object",
            "properties": {
                "type": {"const": "auth"},
                "access_token": STRING,
            },
            "required": ["type", "access_token"],
        },
    },
    "auth_ok": {
        "summary": "The connection is authenticated.",
        "payload": {
            "type": "object",
            "properties": {"type": {"const": "auth_ok"}, "ha_version": STRING},
            "required": ["type", "ha_version"],
        },
    },
    "auth_invalid": {
        "summary": "Authentication failed; the server closes the connection.",
        "payload": {
            "type": "object",
            "properties": {"type": {"const": "auth_invalid"}, "message": STRING},
            "required": ["type", "message"],
        },
    },
}

RESULT_MESSAGE: dict[str, Any] = {
    "summary": "Result of a command.",
    "payload": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "type": {"const": "result"},
            "success": {"type": "boolean"},
            "result": {},
            "error": {
                "type": "object",
                "properties": {
                    "code": STRING,
                    "message": STRING,
                    "translation_key": STRING,
                    "translation_domain": STRING,
                    "translation_placeholders": {"type": "object"},
                },
                "required": ["code", "message"],
            },
        },
        "required": ["id", "type", "success"],
    },
}

EVENT_MESSAGE: dict[str, Any] = {
    "summary": "Event of a subscription, sent with the id of the subscribe command.",
    "payload": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "type": {"const": "event"},
            "event": {},
        },
        "required": ["id", "type", "event"],
    },
}


def build_document(
    handlers: dict[str, tuple[Callable[..., Any], Any]],
    converter: SchemaConverter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the AsyncAPI document and coverage statistics."""
    messages: dict[str, Any] = {
        **AUTH_MESSAGES,
        "result": RESULT_MESSAGE,
        "event": EVENT_MESSAGE,
    }
    operations: dict[str, Any] = {
        "authenticate": {
            "action": "receive",
            "channel": {"$ref": "#/channels/websocket"},
            "messages": [{"$ref": "#/channels/websocket/messages/auth"}],
            "reply": {
                "channel": {"$ref": "#/channels/websocket"},
                "messages": [
                    {"$ref": "#/channels/websocket/messages/auth_ok"},
                    {"$ref": "#/channels/websocket/messages/auth_invalid"},
                ],
            },
        }
    }
    tags: set[str] = set()
    stats: Counter[str] = Counter()
    open_commands: dict[str, list[str]] = {}

    for command, (handler, schema) in sorted(handlers.items()):
        integration = _integration(handler)
        tags.add(integration)
        message_id = _message_id(command)
        if schema is False:
            stats["without_schema"] += 1
            payload: dict[str, Any] = {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "type": {"const": command}},
                "required": ["id", "type"],
            }
        else:
            payload = converter.convert(schema)
            if fields := _open_fields(payload):
                open_commands[command] = fields
        stats["commands"] += 1
        message: dict[str, Any] = {
            "name": command,
            "summary": command,
            "tags": [{"name": integration}],
            "payload": payload,
        }
        if doc := inspect.getdoc(handler):
            summary, _, description = doc.partition("\n")
            message["summary"] = summary
            if description := description.strip():
                message["description"] = description
        messages[message_id] = message
        replies = [{"$ref": "#/channels/websocket/messages/result"}]
        if _is_subscription(command):
            replies.append({"$ref": "#/channels/websocket/messages/event"})
        operations[message_id] = {
            "action": "receive",
            "channel": {"$ref": "#/channels/websocket"},
            "messages": [{"$ref": f"#/channels/websocket/messages/{message_id}"}],
            "tags": [{"name": integration}],
            "reply": {
                "channel": {"$ref": "#/channels/websocket"},
                "messages": replies,
            },
        }

    document = {
        "asyncapi": "3.0.0",
        "info": {
            "title": "Home Assistant WebSocket API",
            "version": __version__,
            "description": (
                "Generated from the WebSocket commands registered by the loaded"
                " integrations. Responses and events are not described yet."
            ),
            "tags": [{"name": tag} for tag in sorted(tags)],
        },
        "servers": {
            "local": {
                "host": "homeassistant.local:8123",
                "protocol": "ws",
                "pathname": "/api/websocket",
            }
        },
        "channels": {
            "websocket": {
                "address": "/api/websocket",
                "messages": {
                    message_id: {"$ref": f"#/components/messages/{message_id}"}
                    for message_id in messages
                },
            }
        },
        "operations": operations,
        "components": {"messages": messages},
    }
    coverage = {
        "commands": stats["commands"],
        "without_schema": stats["without_schema"],
        "with_open_fields": len(open_commands),
        "open_fields": sum(len(fields) for fields in open_commands.values()),
        "unknown_validators": dict(converter.unknown.most_common()),
        "open_commands": open_commands,
    }
    return document, coverage


async def _async_collect(
    config_dir: str, integrations: list[str]
) -> tuple[dict[str, tuple[Callable[..., Any], Any]], list[str]]:
    hass: HomeAssistant | None = await async_setup_hass(
        RuntimeConfig(config_dir=config_dir, skip_pip=True)
    )
    if hass is None:
        raise RuntimeError("Home Assistant failed to start")
    await hass.async_block_till_done()
    handlers = dict(hass.data["websocket_api"])
    missing = [
        domain for domain in integrations if domain not in hass.config.components
    ]
    await hass.async_stop(force=True)
    return handlers, missing


def main() -> int:
    """Generate the document."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Path of the AsyncAPI JSON document")
    parser.add_argument(
        "--integrations",
        nargs="+",
        default=DEFAULT_INTEGRATIONS,
        help="Integrations to load",
    )
    parser.add_argument(
        "--coverage", type=Path, help="Write coverage details to this file"
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as config_dir:
        lines = [f"{domain}:" for domain in args.integrations if domain != "recorder"]
        if "recorder" in args.integrations:
            lines += [
                "recorder:",
                f"  db_url: sqlite:///{config_dir}/home-assistant_v2.db",
            ]
        Path(config_dir, "configuration.yaml").write_text("\n".join(lines) + "\n")
        # Home Assistant flags blocking calls in the thread it ran in, so it gets its own.
        with ThreadPoolExecutor(1) as executor:
            handlers, missing = executor.submit(
                asyncio.run, _async_collect(config_dir, args.integrations)
            ).result()
    document, coverage = build_document(handlers, SchemaConverter())
    args.output.write_text(json.dumps(document, indent=2) + "\n")
    if args.coverage:
        args.coverage.write_text(json.dumps(coverage, indent=2) + "\n")

    print(f"Integrations not loaded: {', '.join(missing) or 'none'}")
    print(
        f"Commands: {coverage['commands']}, without schema: {coverage['without_schema']},"
        f" with open fields: {coverage['with_open_fields']}"
        f" ({coverage['open_fields']} fields)"
    )
    for name, count in list(coverage["unknown_validators"].items())[:15]:
        print(f"  undescribed validator {name}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
