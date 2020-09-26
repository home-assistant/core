"""Middleware to set the request context."""

from aiohttp.web import middleware

from homeassistant.core import callback

# mypy: allow-untyped-defs


@callback
def setup_request_context(app, context):
    """Create request context middleware for the app."""

    @middleware
    async def request_context_middleware(request, handler):
        """Request context middleware."""
        context.set(request)
        return await handler(request)

    app.middlewares.append(request_context_middleware)
