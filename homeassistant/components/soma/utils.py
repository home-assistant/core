"""Soma helpers functions."""


def is_api_response_success(apiResponse: dict) -> bool:
    """Check if the response returned from the Connect API is a success or not."""
    return ("result" in apiResponse) and (apiResponse["result"].lower() == "success")
