"""Tests for the OpenAI Conversation entity."""

from pathlib import Path
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.openai_conversation.entity import (
    _format_structured_output,
    async_prepare_files_for_prompt,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector


async def test_format_structured_output() -> None:
    """Test the format_structured_output function."""
    schema = vol.Schema(
        {
            vol.Required("name"): selector.TextSelector(),
            vol.Optional("age"): selector.NumberSelector(
                config=selector.NumberSelectorConfig(
                    min=0,
                    max=120,
                ),
            ),
            vol.Required("stuff"): selector.ObjectSelector(
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
                    "strict": True,
                },
                "type": "array",
            },
        },
        "required": [
            "name",
            "stuff",
            "age",
        ],
        "strict": True,
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
            "document.pdf",
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
    ("filename", "exists", "mime_type", "error"),
    [
        pytest.param("image.jpg", False, None, "does not exist", id="missing_file"),
        pytest.param(
            "document.txt",
            True,
            None,
            "not an image file or PDF",
            id="unsupported_inferred_mime_type",
        ),
        pytest.param(
            "document.unknown_openai_attachment",
            True,
            None,
            "not an image file or PDF",
            id="unknown_mime_type",
        ),
        pytest.param(
            "image.jpg",
            True,
            "text/plain",
            "not an image file or PDF",
            id="unsupported_explicit_mime_type",
        ),
    ],
)
async def test_prepare_files_for_prompt_invalid_file(
    hass: HomeAssistant,
    filename: str,
    exists: bool,
    mime_type: str | None,
    error: str,
) -> None:
    """Test missing files and unsupported attachment types."""
    with (
        patch("pathlib.Path.exists", return_value=exists),
        pytest.raises(HomeAssistantError, match=error),
    ):
        await async_prepare_files_for_prompt(hass, [(Path(filename), mime_type)])
