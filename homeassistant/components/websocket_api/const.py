"""Websocket constants."""
import asyncio
from concurrent import futures

DOMAIN = 'websocket_api'
URL = '/api/websocket'
MAX_PENDING_MSG = 512

ERR_ID_REUSE = 1
ERR_INVALID_FORMAT = 2
ERR_NOT_FOUND = 3
ERR_UNKNOWN_COMMAND = 4
ERR_UNKNOWN_ERROR = 5

TYPE_RESULT = 'result'

# Define the possible errors that occur when connections are cancelled.
# Originally, this was just asyncio.CancelledError, but issue #9546 showed
# that futures.CancelledErrors can also occur in some situations.
CANCELLATION_ERRORS = (asyncio.CancelledError, futures.CancelledError)
