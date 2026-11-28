"""Tests for the Azure OpenAI Conversation entity."""

from pathlib import Path
from unittest.mock import patch

from openai.types.responses import ResponseTextDeltaEvent, ResponseTextDoneEvent
import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.azure_openai.const import DOMAIN
from homeassistant.components.azure_openai.entity import (
    _convert_content_to_param,
    _filter_citations,
    _format_structured_output,
    _transform_stream,
    async_prepare_files_for_prompt,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm, selector
from homeassistant.util.json import JsonObjectType


@pytest.mark.parametrize(
    ("chunks", "expected"),
    [
        pytest.param(
            ["Text ([source](https://example.com/)) end"],
            "Text end",
            id="single",
        ),
        pytest.param(
            ["Text ([source](", "https://example.com/)) end"],
            "Text end",
            id="split",
        ),
        pytest.param(
            ["A ([one](https://one/)) B ([two](https://two/)) C"],
            "A B C",
            id="multiple",
        ),
        pytest.param(
            ["A ([source](https://example.com/a_(", "b))) tail"],
            "A tail",
            id="parenthesized-url",
        ),
        pytest.param(
            ["Text ([source"],
            "Text ([source",
            id="incomplete-label",
        ),
        pytest.param(
            ["Text ([source](ftp://example.com/)) end"],
            "Text ([source](ftp://example.com/)) end",
            id="unsupported-scheme",
        ),
        pytest.param(
            [r"Text ([source](https://example.com/a\)b)) end"],
            "Text end",
            id="escaped-parenthesis",
        ),
        pytest.param(
            ["Text ([source](https://example.com/) end"],
            "Text ([source](https://example.com/) end",
            id="malformed-closing-parenthesis",
        ),
    ],
)
def test_filter_citations(chunks: list[str], expected: str) -> None:
    """Test citations are removed across arbitrary text chunks."""
    output = ""
    pending = ""
    for chunk in chunks:
        emitted, pending = _filter_citations(pending + chunk)
        output += emitted
    emitted, pending = _filter_citations(pending, final=True)
    assert output + emitted == expected
    assert pending == ""


async def test_filter_citations_tracks_each_output() -> None:
    """Test citation buffering does not consume text from another output."""

    async def events():
        yield ResponseTextDeltaEvent(
            content_index=0,
            delta="A ([one](",
            item_id="a",
            logprobs=[],
            output_index=0,
            sequence_number=0,
            type="response.output_text.delta",
        )
        yield ResponseTextDeltaEvent(
            content_index=0,
            delta=") visible",
            item_id="b",
            logprobs=[],
            output_index=1,
            sequence_number=1,
            type="response.output_text.delta",
        )
        yield ResponseTextDeltaEvent(
            content_index=0,
            delta="https://one/)) end",
            item_id="a",
            logprobs=[],
            output_index=0,
            sequence_number=2,
            type="response.output_text.delta",
        )
        for sequence_number, item_id, output_index in ((3, "a", 0), (4, "b", 1)):
            yield ResponseTextDoneEvent(
                content_index=0,
                item_id=item_id,
                logprobs=[],
                output_index=output_index,
                sequence_number=sequence_number,
                text="",
                type="response.output_text.done",
            )

    assert [
        item["content"]
        async for item in _transform_stream(None, events(), remove_citations=True)
    ] == ["A", ") visible", " end"]


@pytest.mark.parametrize(
    ("code", "outputs", "error", "external", "status"),
    [
        pytest.param(None, None, False, True, "completed", id="no_output"),
        pytest.param(
            "raise ValueError()",
            [{"type": "logs", "logs": "ValueError"}],
            True,
            True,
            "failed",
            id="failed",
        ),
        pytest.param(
            "plt.show()",
            [{"type": "image", "url": "https://example.com/plot.png"}],
            False,
            True,
            "completed",
            id="image",
        ),
        pytest.param("print(1)", None, False, False, "completed", id="custom_function"),
        pytest.param("print(1)", None, False, True, "incomplete", id="incomplete"),
    ],
)
def test_convert_code_interpreter(
    code: str | None,
    outputs: list[JsonObjectType] | None,
    error: bool,
    external: bool,
    status: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Restore native external calls while preserving custom function calls."""
    content = [
        conversation.AssistantContent(
            agent_id="conversation.azure_openai",
            tool_calls=[
                llm.ToolInput(
                    id="ci_A",
                    tool_name="code_interpreter",
                    tool_args={"code": code},
                    external=external,
                )
            ],
        ),
        conversation.ToolResultContent(
            agent_id="conversation.azure_openai",
            tool_call_id="ci_A",
            tool_name="code_interpreter",
            result=llm.ToolResult(
                data={"container_id": "cntr_A", "output": outputs, "status": status},
                error=error,
            ),
        ),
    ]

    assert _convert_content_to_param(content) == snapshot


async def test_format_structured_output() -> None:
    """Test the format_structured_output function."""
    schema = probatio.Schema(
        {
            probatio.Required("name"): selector.TextSelector(),
            probatio.Optional("age"): selector.NumberSelector(
                config=selector.NumberSelectorConfig(
                    min=0,
                    max=120,
                ),
            ),
            probatio.Required("stuff"): selector.ObjectSelector(
                {
                    "multiple": True,
                    "fields": {
                        "item_name": {
                            "selector": {"text": None},
                        },
                        "item_value": {
                            "selector": {"text": None},
                        },
                    },
                }
            ),
        }
    )
    assert _format_structured_output(schema, None) == {
        "additionalProperties": False,
        "properties": {
            "age": {
                "maximum": 120.0,
                "minimum": 0.0,
                "type": [
                    "number",
                    "null",
                ],
            },
            "name": {
                "type": "string",
            },
            "stuff": {
                "items": {
                    "properties": {
                        "item_name": {
                            "type": ["string", "null"],
                        },
                        "item_value": {
                            "type": ["string", "null"],
                        },
                    },
                    "required": [
                        "item_name",
                        "item_value",
                    ],
                    "type": "object",
                    "additionalProperties": False,
                },
                "type": "array",
            },
        },
        "required": [
            "name",
            "stuff",
            "age",
        ],
        "type": "object",
    }


@pytest.mark.parametrize(
    ("filename", "expected_content"),
    [
        pytest.param(
            "image.jpg",
            {
                "type": "input_image",
                "image_url": "data:image/jpeg;base64,QUJD",
                "detail": "auto",
            },
            id="jpeg",
        ),
        pytest.param(
            "/config/media/documents/document.pdf",
            {
                "type": "input_file",
                "filename": "document.pdf",
                "file_data": "data:application/pdf;base64,QUJD",
            },
            id="pdf",
        ),
    ],
)
async def test_prepare_files_for_prompt_infers_mime_type(
    hass: HomeAssistant,
    filename: str,
    expected_content: dict[str, str],
) -> None:
    """Test attachments without an explicit MIME type."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"ABC"),
    ):
        assert await async_prepare_files_for_prompt(hass, [(Path(filename), None)]) == [
            expected_content
        ]


@pytest.mark.parametrize(
    "mime_type",
    [
        "application/pdf",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    ],
)
async def test_prepare_files_for_prompt_supported_mime_type(
    hass: HomeAssistant,
    mime_type: str,
) -> None:
    """Test supported attachment MIME types are accepted."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"ABC"),
    ):
        result = await async_prepare_files_for_prompt(
            hass, [(Path("attachment"), mime_type)]
        )

    assert len(result) == 1


@pytest.mark.parametrize(
    ("filename", "exists", "mime_type", "translation_key"),
    [
        pytest.param("image.jpg", False, None, "attachment_missing", id="missing_file"),
        pytest.param(
            "document.txt",
            True,
            None,
            "attachment_unsupported",
            id="unsupported_inferred_mime_type",
        ),
        pytest.param(
            "document.unknown_openai_attachment",
            True,
            None,
            "attachment_unsupported",
            id="unknown_mime_type",
        ),
        pytest.param(
            "image.jpg",
            True,
            "text/plain",
            "attachment_unsupported",
            id="unsupported_explicit_mime_type",
        ),
        pytest.param(
            "image.svg",
            True,
            "image/svg+xml",
            "attachment_unsupported",
            id="unsupported_image_mime_type",
        ),
        pytest.param(
            "document.pdf",
            True,
            "application/pdf-other",
            "attachment_unsupported",
            id="pdf_prefix",
        ),
    ],
)
async def test_prepare_files_for_prompt_invalid_file(
    hass: HomeAssistant,
    filename: str,
    exists: bool,
    mime_type: str | None,
    translation_key: str,
) -> None:
    """Test missing files and unsupported attachment types."""
    with (
        patch("pathlib.Path.exists", return_value=exists),
        pytest.raises(HomeAssistantError) as err,
    ):
        await async_prepare_files_for_prompt(hass, [(Path(filename), mime_type)])

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    assert err.value.translation_placeholders == {"file_path": filename}
