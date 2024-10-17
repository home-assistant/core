"""Test for utility functions of the Bring! integration."""

from typing import cast

from bring_api import BringUserSettingsResponse
import pytest

from homeassistant.components.bring import DOMAIN
from homeassistant.components.bring.coordinator import BringData
from homeassistant.components.bring.util import list_language, sum_attributes

from tests.common import load_json_object_fixture


@pytest.mark.parametrize(
    ("list_uuid", "expected"),
    [
        ("e542eef6-dba7-4c31-a52c-29e6ab9d83a5", "de-DE"),
        ("b4776778-7f6c-496e-951b-92a35d3db0dd", "en-US"),
        ("00000000-0000-0000-0000-00000000", None),
    ],
)
def test_list_language(list_uuid: str, expected: str | None) -> None:
    """Test function list_language."""

    result = list_language(
        list_uuid,
        cast(
            BringUserSettingsResponse,
            load_json_object_fixture("usersettings.json", DOMAIN),
        ),
    )

    assert result == expected


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        ("urgent", 2),
        ("convenient", 2),
        ("discounted", 2),
    ],
)
def test_sum_attributes(attribute: str, expected: int) -> None:
    """Test function sum_attributes."""

    result = sum_attributes(
        cast(
            BringData,
            load_json_object_fixture("items.json", DOMAIN),
        ),
        attribute,
    )

    assert result == expected
