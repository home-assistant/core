"""Tests for the Twilio Call notify platform."""

import probatio
import pytest

from homeassistant.components.twilio_call.notify import (
    CONF_FROM_NUMBER,
    PLATFORM_SCHEMA,
)
from homeassistant.util.yaml import parse_yaml


@pytest.mark.parametrize(
    "from_number",
    [
        pytest.param("+441234567890", id="quoted"),
        # YAML reads an unquoted +441234567890 as the int 441234567890
        pytest.param(parse_yaml("n: +441234567890")["n"], id="unquoted"),
    ],
)
def test_from_number_accepts_e164(from_number: str | int) -> None:
    """Test the from number is accepted whether or not it is quoted in YAML."""
    config = PLATFORM_SCHEMA({"platform": "twilio_call", CONF_FROM_NUMBER: from_number})

    assert config[CONF_FROM_NUMBER] == "+441234567890"


@pytest.mark.parametrize(
    "from_number",
    [
        pytest.param("441234567890", id="no_plus"),
        pytest.param("+44 1234 567890", id="spaces"),
        pytest.param(True, id="bool"),
    ],
)
def test_from_number_rejects_invalid(from_number: str | bool) -> None:
    """Test a from number that is not in E.164 format is rejected."""
    with pytest.raises(probatio.Invalid, match="phone number"):
        PLATFORM_SCHEMA({"platform": "twilio_call", CONF_FROM_NUMBER: from_number})
