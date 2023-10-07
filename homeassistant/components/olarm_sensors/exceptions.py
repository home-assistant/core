"""Module that stores all the exceptions in Home Assistant format."""
from aiohttp import ClientConnectorError, ContentTypeError
from aiohttp.client_reqrep import ClientResponse, RequestInfo
from aiohttp.typedefs import LooseHeaders
from aiohttp.web_exceptions import HTTPForbidden, HTTPMethodNotAllowed, HTTPNotFound


class ListIndexError(IndexError, BaseException):
    """Index Error for Olarm."""

    def __init__(self) -> None:
        """Index Error for Olarm."""


class CodeTypeError(TypeError, BaseException):
    """Alarm Code Error for Olarm."""

    def __init__(self) -> None:
        """Alarm Code Error for Olarm."""


class DictionaryKeyError(KeyError, BaseException):
    """Key Error for Olarm."""

    def __init__(self) -> None:
        """Key Error for Olarm."""


class APINotFoundError(HTTPNotFound, BaseException):
    """HTTP 404 not found error."""

    def __init__(self) -> None:
        """HTTP 404 not found error."""
        super().__init__()


class APIForbiddenError(HTTPForbidden, BaseException):
    """HTTP 403 Forbidden error."""

    def __init__(self) -> None:
        """HTTP 403 Forbidden error."""
        super().__init__()


class APIMethodError(HTTPMethodNotAllowed, BaseException):
    """HTTP 405 Wrong Method error."""

    def __init__(self, method=None, allowed_methods=None) -> None:
        """HTTP 405 Wrong Method error."""
        super().__init__(method, allowed_methods)


class APIClientConnectorError(ClientConnectorError, BaseException):
    """HTTP Client error."""

    def __init__(self, connection_key=None, os_error=None) -> None:
        """HTTP Client error."""
        super().__init__(connection_key, os_error)


class APIContentTypeError(ContentTypeError, BaseException):
    """HTTP content error."""

    def __init__(
        self,
        request_info: RequestInfo,
        history: tuple[ClientResponse, ...],
        *,
        code: int | None = None,
        status: int | None = None,
        message: str = "",
        headers: LooseHeaders | None = None,
    ) -> None:
        """HTTP Content error."""
        super().__init__(
            request_info,
            history,
            code=code,
            status=status,
            message=message,
            headers=headers,
        )
