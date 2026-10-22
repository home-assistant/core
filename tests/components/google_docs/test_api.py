"""Test real Google client requests and document text extraction."""

import json
from unittest.mock import MagicMock, patch

from httplib2 import Response
import pytest

from homeassistant.components.google_docs import api


@pytest.fixture
def http_client() -> MagicMock:
    """Use the real discovery client while replacing only its HTTP transport."""
    client = MagicMock()
    client.request.return_value = (
        Response({"status": "200", "content-type": "application/json"}),
        b'{"documentId": "test-document", "title": "Home Assistant"}',
    )
    return client


def test_create_document(http_client: MagicMock) -> None:
    """Creation uses Google's real client method and does not retry a write."""
    with patch("googleapiclient._auth.authorized_http", return_value=http_client):
        document = api.create_document("access-token")
    assert document["documentId"] == "test-document"
    args, kwargs = http_client.request.call_args
    assert args[0].startswith("https://docs.googleapis.com/v1/documents?")
    assert args[1] == "POST"
    assert json.loads(kwargs["body"]) == {"title": "Home Assistant"}
    assert http_client.request.call_count == 1
    http_client.close.assert_called_once()


@pytest.mark.parametrize(
    ("include_content", "fields"),
    [(True, "documentId%2Ctitle%2Cbody"), (False, "documentId%2Ctitle")],
)
def test_get_document(
    http_client: MagicMock, include_content: bool, fields: str
) -> None:
    """Reads select the configured document and the requested content scope."""
    with patch("googleapiclient._auth.authorized_http", return_value=http_client):
        api.get_document("access-token", "test-document", include_content)
    args, _kwargs = http_client.request.call_args
    assert args[0].startswith("https://docs.googleapis.com/v1/documents/test-document?")
    assert f"fields={fields}" in args[0]
    assert args[1] == "GET"
    http_client.close.assert_called_once()


def test_append_text_uses_current_end(http_client: MagicMock) -> None:
    """Appending uses the server's current end rather than a stale text index."""
    with patch("googleapiclient._auth.authorized_http", return_value=http_client):
        api.append_text("access-token", "test-document", "שלום 🌍\nAnother line\n")
    args, kwargs = http_client.request.call_args
    assert args[0].startswith(
        "https://docs.googleapis.com/v1/documents/test-document:batchUpdate?"
    )
    assert args[1] == "POST"
    assert json.loads(kwargs["body"]) == {
        "requests": [
            {
                "insertText": {
                    "endOfSegmentLocation": {},
                    "text": "שלום 🌍\nAnother line\n",
                }
            }
        ]
    }
    assert http_client.request.call_count == 1
    http_client.close.assert_called_once()


def test_failed_append_is_not_retried(http_client: MagicMock) -> None:
    """An uncertain write outcome must not silently duplicate appended text."""
    http_client.request.side_effect = TimeoutError
    with (
        patch("googleapiclient._auth.authorized_http", return_value=http_client),
        pytest.raises(TimeoutError),
    ):
        api.append_text("access-token", "test-document", "One entry")
    assert http_client.request.call_count == 1
    http_client.close.assert_called_once()


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ([], ""),
        ([{"paragraph": {"elements": [{"textRun": {"content": "\n"}}]}}], ""),
        (
            [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "שלום 🌍"}},
                            {"inlineObjectElement": {"inlineObjectId": "image"}},
                            {"textRun": {"content": "\nLine two\n\n"}},
                        ]
                    }
                }
            ],
            "שלום 🌍\nLine two\n",
        ),
        (
            [
                {
                    "table": {
                        "tableRows": [
                            {
                                "tableCells": [
                                    {
                                        "content": [
                                            {
                                                "paragraph": {
                                                    "elements": [
                                                        {
                                                            "textRun": {
                                                                "content": "Cell\n"
                                                            }
                                                        }
                                                    ]
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                },
                {
                    "tableOfContents": {
                        "content": [
                            {
                                "paragraph": {
                                    "elements": [{"textRun": {"content": "Heading\n"}}]
                                }
                            }
                        ]
                    }
                },
                {"paragraph": {"elements": [{"textRun": {"content": "\n"}}]}},
            ],
            "Cell\nHeading\n",
        ),
        ([{"sectionBreak": {}}], ""),
    ],
)
def test_document_text(content: list[dict], expected: str) -> None:
    """Plain text preserves Unicode and user newlines across document structures."""
    assert api.document_text({"body": {"content": content}}) == expected


def test_document_without_body() -> None:
    """An empty document response has no readable body text."""
    assert api.document_text({}) == ""
