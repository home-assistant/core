"""Test utilities."""
from collections.abc import Awaitable, Callable

from aiohttp.web import Application, Request, StreamResponse, middleware


def mock_real_ip(app: Application) -> Callable[[str], None]:
    """Inject middleware to mock real IP.

    Returns a function to set the real IP.
    """
    ip_to_mock: str | None = None

    def set_ip_to_mock(value: str):
        nonlocal ip_to_mock
        ip_to_mock = value

    @middleware
    async def mock_real_ip(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Mock Real IP middleware."""
        nonlocal ip_to_mock

        request = request.clone(remote=ip_to_mock)

        return await handler(request)

    async def real_ip_startup(app):
        """Startup of real ip."""
        app.middlewares.insert(0, mock_real_ip)

    app.on_startup.append(real_ip_startup)

    return set_ip_to_mock
