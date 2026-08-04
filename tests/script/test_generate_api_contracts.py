"""Tests for Hassfest API contract generation."""

import ast
import json
from pathlib import Path

import pytest

from script.hassfest.api_contracts import ASYNCAPI_PATH, OPENAPI_PATH, _documents
from script.hassfest.api_contracts.common import SourceIndex
from script.hassfest.api_contracts.schema import (
    annotation_schema,
    mapping_schema,
    schema_mapping,
)
from script.hassfest.model import Config, Integration

ROOT = Path(__file__).parents[2]


def _generated() -> dict[Path, str]:
    config = Config(
        specific_integrations=None,
        root=ROOT,
        action="validate",
        requirements=False,
    )
    integrations = Integration.load_dir(config.core_integrations_path, config)
    return _documents(integrations, config)


@pytest.mark.timeout(30)  # A full source scan can exceed the global 9-second limit.
def test_generated_contracts_are_current() -> None:
    """Test committed API contracts match route metadata."""
    documents = _generated()
    assert (ROOT / OPENAPI_PATH).read_text() == documents[OPENAPI_PATH]
    assert (ROOT / ASYNCAPI_PATH).read_text() == documents[ASYNCAPI_PATH]


def test_contracts_cover_core_interfaces() -> None:
    """Test representative HTTP, webhook, WebSocket, and SSE interfaces."""
    openapi = json.loads((ROOT / OPENAPI_PATH).read_bytes())
    asyncapi = json.loads((ROOT / ASYNCAPI_PATH).read_bytes())

    assert openapi["openapi"] == "3.1.0"
    assert openapi["paths"]["/api/"]["get"]["tags"] == ["api"]
    assert "/openapi.json" not in openapi["paths"]
    assert "/api/camera_proxy/{entity_id}" in openapi["paths"]
    assert set(openapi["paths"]["/api/webhook/{webhook_id}"]) == {
        "get",
        "head",
        "post",
        "put",
    }
    grouped_tags = [tag for group in openapi["x-tagGroups"] for tag in group["tags"]]
    assert sorted(grouped_tags) == sorted(tag["name"] for tag in openapi["tags"])
    assert len(grouped_tags) == len(set(grouped_tags))

    assert asyncapi["asyncapi"] == "3.1.0"
    assert asyncapi["servers"]["secure_websocket"]["protocol"] == "wss"
    assert asyncapi["servers"]["https"]["protocol"] == "https"
    assert {"$ref": "#/servers/secure_websocket"} in asyncapi["channels"]["websocket"][
        "servers"
    ]
    assert "subscribe_events" in asyncapi["components"]["messages"]
    assert asyncapi["channels"]["event_stream"]["address"] == "/api/stream"
    assert {"$ref": "#/servers/https"} in asyncapi["channels"]["event_stream"][
        "servers"
    ]
    assert asyncapi["operations"]["send_event_stream"][
        "x-home-assistant-requires-admin"
    ]
    usage_prediction = asyncapi["components"]["messages"][
        "usage_prediction_common_control"
    ]
    assert usage_prediction["name"] == "usage_prediction/common_control"
    for operation in asyncapi["operations"].values():
        if operation.get("tags"):
            assert operation["action"] == "receive"
            assert operation["title"]

    # Plain Voluptuous keys are optional; only explicit Required markers are required.
    assert asyncapi["components"]["messages"]["automation_config"]["payload"][
        "required"
    ] == ["id", "type"]
    assert (
        "preferences"
        in asyncapi["components"]["messages"]["analytics_preferences"]["payload"][
            "required"
        ]
    )
    extract = asyncapi["components"]["messages"]["extract_from_target"]
    assert extract["payload"]["properties"]["target"]["properties"]["entity_id"][
        "items"
    ] == {"type": "string"}
    entity = asyncapi["components"]["messages"][
        "config_entity_registry_list_for_display_result"
    ]["payload"]["properties"]["result"]["properties"]["entities"]["items"]
    assert entity["required"] == ["ei", "pl"]
    assert entity["properties"]["dp"]["type"] == "integer"
    assert "#L" in entity["properties"]["dp"]["description"]
    extract_reply = asyncapi["operations"]["receive_extract_from_target"]["reply"]
    assert extract_reply == {
        "channel": {"$ref": "#/channels/extract_from_target_reply"},
        "messages": [
            {
                "$ref": "#/channels/extract_from_target_reply/messages/extract_from_target_result"
            },
            {"$ref": "#/channels/extract_from_target_reply/messages/result_error"},
        ],
    }
    assert set(asyncapi["channels"]["extract_from_target_reply"]["messages"]) == {
        "extract_from_target_result",
        "result_error",
    }
    assert asyncapi["channels"]["extract_from_target_reply"]["servers"] == [
        {"$ref": "#/servers/websocket"},
        {"$ref": "#/servers/secure_websocket"},
    ]
    assert (
        "extract_from_target_result"
        not in asyncapi["channels"]["websocket"]["messages"]
    )
    assert (
        asyncapi["components"]["messages"]["result_error"]["payload"]["properties"][
            "success"
        ]["const"]
        is False
    )
    recorder = asyncapi["components"]["messages"]["recorder_import_statistics"][
        "payload"
    ]
    assert recorder["additionalProperties"] is False
    stats = recorder["properties"]["stats"]["items"]
    assert "start" in stats["properties"]
    assert "start" in stats["required"]
    assert "oneOf" not in json.dumps(recorder)
    assert {
        schema["type"]
        for schema in recorder["properties"]["stats"]["items"]["properties"]["mean"][
            "anyOf"
        ]
    } == {"integer", "number"}
    intent_response = openapi["paths"]["/api/intent/handle"]["post"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert intent_response["properties"]["response_type"]["enum"] == [
        "action_done",
        "partial_action_done",
        "query_answer",
        "error",
    ]
    assert openapi["paths"]["/api/conversation/process"]["post"]["requestBody"][
        "required"
    ]
    assert (
        openapi["paths"]["/api/config/config_entries/flow"]["post"]["requestBody"][
            "content"
        ]["application/json"]["schema"]["additionalProperties"]
        is True
    )
    assert openapi["paths"]["/api/diagnostics/{d_type}/{d_id}"]["get"][
        "x-home-assistant-requires-admin"
    ]
    assert "github.com/home-assistant/core/blob/dev/" in intent_response["description"]
    update_location = openapi["components"]["schemas"]["mobile_app_update_location"][
        "properties"
    ]["data"]
    assert update_location["properties"]["gps"]["prefixItems"] == [
        {"type": "number", "minimum": -90, "maximum": 90},
        {"type": "number", "minimum": -180, "maximum": 180},
    ]
    assert update_location["properties"]["gps_accuracy"]["minimum"] == 0
    assert (
        "GPS accuracy" in update_location["properties"]["gps_accuracy"]["description"]
    )
    assert "/tests/" not in json.dumps(openapi)
    assert "/tests/" not in json.dumps(asyncapi)
    assert asyncapi["operations"]["send_event_stream"]["messages"]


def test_source_index_allows_repeated_constants(tmp_path: Path) -> None:
    """Test sibling references are not mistaken for a recursive constant."""
    package = tmp_path / "homeassistant"
    package.mkdir()
    (package / "demo.py").write_text('ITEM = "value"\nPAIR = [ITEM, ITEM]\n')

    index = SourceIndex(tmp_path)

    assert index.value(
        "homeassistant.demo", index.assignments[("homeassistant.demo", "PAIR")]
    ) == ["value", "value"]


def test_source_index_resolves_relative_imports_and_literals(tmp_path: Path) -> None:
    """Test static values resolve across relative imports without executing code."""
    package = tmp_path / "homeassistant"
    package.mkdir()
    (package / "const.py").write_text("VALUE = -2\n")
    (package / "demo.py").write_text("from .const import VALUE\nRESULT = VALUE\n")

    index = SourceIndex(tmp_path)

    assert (
        index.value(
            "homeassistant.demo", index.assignments[("homeassistant.demo", "RESULT")]
        )
        == -2
    )


def test_annotation_schema_preserves_requiredness(tmp_path: Path) -> None:
    """Test generated types do not invent required fields or enums."""
    package = tmp_path / "homeassistant"
    package.mkdir()
    (package / "demo.py").write_text(
        """\
class OptionalPayload(TypedDict, total=False):
    value: str

@dataclass
class Payload:
    required: str
    optional: int = 0

class Constants:
    VALUE = "value"
"""
    )
    index = SourceIndex(tmp_path)
    module = "homeassistant.demo"

    optional = annotation_schema(index, module, ast.Name(id="OptionalPayload"))
    payload = annotation_schema(index, module, ast.Name(id="Payload"))

    assert "required" not in optional
    assert payload["required"] == ["required"]
    assert annotation_schema(index, module, ast.Name(id="str")) == {"type": "string"}
    assert annotation_schema(index, module, ast.Name(id="Constants")) == {}


def test_voluptuous_schema_preserves_validation_semantics(tmp_path: Path) -> None:
    """Test literals, alternatives, unknown fields, and extra-key policy."""
    package = tmp_path / "homeassistant"
    package.mkdir()
    (package / "demo.py").write_text(
        """\
SCHEMA = vol.Schema(
    {
        vol.Required("fixed"): "value",
        vol.Required("number"): vol.Any(float, int),
        vol.Required("nullable"): vol.Any(None, str),
        vol.Required("unknown"): cv.datetime,
    },
    extra=vol.ALLOW_EXTRA,
)
PLAIN = {vol.Required("value"): str}
"""
    )
    index = SourceIndex(tmp_path)
    module = "homeassistant.demo"

    schema = schema_mapping(index, module, index.assignments[(module, "SCHEMA")])
    assert schema is not None
    rendered = mapping_schema(index, *schema)

    assert rendered["additionalProperties"] is True
    assert rendered["properties"]["fixed"]["const"] == "value"
    assert {item["type"] for item in rendered["properties"]["number"]["anyOf"]} == {
        "integer",
        "number",
    }
    assert {item["type"] for item in rendered["properties"]["nullable"]["anyOf"]} == {
        "null",
        "string",
    }
    assert "unknown" in rendered["properties"]
    assert "unknown" in rendered["required"]

    plain_schema = schema_mapping(index, module, index.assignments[(module, "PLAIN")])
    assert plain_schema is not None
    plain_module, plain, _ = plain_schema
    assert mapping_schema(index, plain_module, plain)["additionalProperties"] is False
