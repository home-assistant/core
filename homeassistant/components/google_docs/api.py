"""Google Docs operations using Google's official Python client."""

from typing import Any, cast

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error

from .const import DEFAULT_DOCUMENT_NAME

API_ERRORS = (GoogleAuthError, HttpError, HttpLib2Error, OSError)


def create_document(access_token: str) -> dict[str, Any]:
    """Create the document for a configuration entry in the executor."""
    with build(
        "docs",
        "v1",
        credentials=Credentials(access_token),  # type: ignore[no-untyped-call]
        cache_discovery=False,
    ) as resource:
        return cast(
            dict[str, Any],
            resource.documents()
            .create(body={"title": DEFAULT_DOCUMENT_NAME}, fields="documentId,title")
            .execute(num_retries=0),
        )


def get_document(
    access_token: str, document_id: str, include_content: bool = True
) -> dict[str, Any]:
    """Read the first document tab, or just its metadata, in the executor."""
    fields = "documentId,title,body" if include_content else "documentId,title"
    with build(
        "docs",
        "v1",
        credentials=Credentials(access_token),  # type: ignore[no-untyped-call]
        cache_discovery=False,
    ) as resource:
        return cast(
            dict[str, Any],
            resource.documents()
            .get(documentId=document_id, fields=fields)
            .execute(num_retries=0),
        )


def append_text(access_token: str, document_id: str, text: str) -> None:
    """Append text at the current end of the first tab in the executor."""
    with build(
        "docs",
        "v1",
        credentials=Credentials(access_token),  # type: ignore[no-untyped-call]
        cache_discovery=False,
    ) as resource:
        resource.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [{"insertText": {"endOfSegmentLocation": {}, "text": text}}]
            },
        ).execute(num_retries=0)


def document_text(document: dict[str, Any]) -> str:
    """Extract body text without Google's mandatory final newline."""
    return _structural_text(document.get("body", {}).get("content", [])).removesuffix(
        "\n"
    )


def _structural_text(elements: list[dict[str, Any]]) -> str:
    """Read paragraphs, table cells, and tables of contents in document order."""
    parts: list[str] = []
    for element in elements:
        if "paragraph" in element:
            parts.extend(
                item["textRun"]["content"]
                for item in element["paragraph"].get("elements", [])
                if "textRun" in item
            )
        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                parts.extend(
                    _structural_text(cell.get("content", []))
                    for cell in row.get("tableCells", [])
                )
        elif "tableOfContents" in element:
            parts.append(
                _structural_text(element["tableOfContents"].get("content", []))
            )
    return "".join(parts)
