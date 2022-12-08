"""Helper functions for Homematicip Cloud Integration."""


def is_error_response(response) -> bool:
    """Response from async call contains errors or not."""
    if isinstance(response, dict):
        return "errorCode" in response and response["errorCode"] != ""

    return False
