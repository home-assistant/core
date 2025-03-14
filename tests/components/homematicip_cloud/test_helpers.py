"""Test HomematicIP Cloud helper functions."""

import json

from homeassistant.components.homematicip_cloud.helpers import is_error_response


async def test_is_error_response() -> None:
    """Test, if an response is a normal result or an error."""
    assert not is_error_response("True")
    assert not is_error_response(True)
    assert not is_error_response("")
    assert is_error_response(
        json.loads(
            '{"errorCode": "INVALID_NUMBER_PARAMETER_VALUE", "minValue": 0.0, "maxValue": 1.01}'
        )
    )
    assert not is_error_response(json.loads('{"errorCode": ""}'))
