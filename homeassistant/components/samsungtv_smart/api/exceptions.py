class ConnectionFailure(Exception):
    """Error during connection."""
    pass


class ResponseError(Exception):
    """Error in response."""
    pass


class HttpApiError(Exception):
    """Error using HTTP API."""
    pass
