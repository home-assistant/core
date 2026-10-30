"""Test HomematicIP Cloud helper functions."""

import json

from homematicip.connection.rest_connection import RestResult

from homeassistant.components.homematicip_cloud.helpers import get_error_code


async def test_get_error_code() -> None:
    """Test, if an response is a normal result or an error."""
    assert get_error_code("True") is None
    assert get_error_code(True) is None
    assert get_error_code("") is None
    assert (
        get_error_code(
            json.loads(
                '{"errorCode": "INVALID_NUMBER_PARAMETER_VALUE",'
                ' "minValue": 0.0, "maxValue": 1.01}'
            )
        )
        == "INVALID_NUMBER_PARAMETER_VALUE"
    )
    assert get_error_code(json.loads('{"errorCode": ""}')) is None


async def test_get_error_code_rest_result() -> None:
    """Test the results the library returns."""
    assert get_error_code(RestResult(status=200)) is None
    assert (
        get_error_code(
            RestResult(status=400, text='{"errorCode": "CLIENT_ACCESS_DENIED"}')
        )
        == "CLIENT_ACCESS_DENIED"
    )
    assert get_error_code(RestResult(status=503, text="")) == "Service Unavailable"
    assert (
        get_error_code(RestResult(status=403, text='{"errorCode": null}'))
        == "Forbidden"
    )
    assert get_error_code(RestResult(status=-1)) == "No status code"
