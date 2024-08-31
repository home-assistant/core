"""Soma helpers functions."""


def is_api_response_success(api_response: dict) -> bool:
    """Check if the response returned from the Connect API is a success or not."""
    return "result" in api_response and api_response["result"].lower() == "success"
