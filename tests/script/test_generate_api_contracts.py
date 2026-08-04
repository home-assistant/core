"""Tests for Hassfest API contract generation."""

import ast
import json
from pathlib import Path

from script.hassfest.api_contracts import ASYNCAPI_PATH, OPENAPI_PATH, _documents
from script.hassfest.api_contracts.common import SourceIndex
from script.hassfest.api_contracts.schema import annotation_schema
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
    assert "subscribe_events" in asyncapi["components"]["messages"]
    assert asyncapi["channels"]["event_stream"]["address"] == "/api/stream"
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
    assert asyncapi["operations"]["receive_extract_from_target"]["reply"][
        "messages"
    ] == [
        {
            "$ref": "#/channels/websocket/messages/extract_from_target_result",
        }
    ]
    intent_response = openapi["paths"]["/api/intent/handle"]["post"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert intent_response["properties"]["response_type"]["enum"]
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
