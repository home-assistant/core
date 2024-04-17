"""Tests for the Nina integration."""

import json
from typing import Any

from tests.common import load_fixture


def mocked_request_function(url: str) -> dict[str, Any]:
    """Mock of the request function."""
    dummy_response: dict[str, Any] = json.loads(
        load_fixture("sample_warnings.json", "nina")
    )

    dummy_response_details: dict[str, Any] = json.loads(
        load_fixture("sample_warning_details.json", "nina")
    )

    dummy_response_regions: dict[str, Any] = json.loads(
        load_fixture("sample_regions.json", "nina")
    )

    dummy_response_labels: dict[str, Any] = json.loads(
        load_fixture("sample_labels.json", "nina")
    )

    if "https://warnung.bund.de/api31/dashboard/" in url:
        return dummy_response

    if "https://warnung.bund.de/api/appdata/gsb/labels/de_labels.json" in url:
        return dummy_response_labels

    if (
        url
        == "https://www.xrepository.de/api/xrepository/urn:de:bund:destatis:bevoelkerungsstatistik:schluessel:rs_2021-07-31/download/Regionalschl_ssel_2021-07-31.json"
    ):
        return dummy_response_regions

    warning_id = url.replace("https://warnung.bund.de/api31/warnings/", "").replace(
        ".json", ""
    )

    return dummy_response_details[warning_id]
