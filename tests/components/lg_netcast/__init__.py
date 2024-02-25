"""Tests for LG Netcast TV."""
from unittest.mock import patch

from pylgnetcast import AccessTokenError, LgNetCastClient, SessionIdError

FAIL_TO_BIND_IP = "1.2.3.4"

IP_ADDRESS = "192.168.1.239"
DEVICE_TYPE = "TV"
MODEL_NAME = "MockLGModelName"
UNIQUE_ID = "1234"

FAKE_SESSION_ID = "987654321"
FAKE_PIN = "123456"


def _patched_lgnetcast_client(*args, session_error=False, **kwargs):
    client = LgNetCastClient(*args, **kwargs)

    def _get_fake_session_id():
        if not client.access_token:
            raise AccessTokenError("Fake Access Token Requested")
        if session_error:
            raise SessionIdError("Can not get session id from TV.")
        return FAKE_SESSION_ID

    client._get_session_id = _get_fake_session_id

    return client


def _patch_lg_netcast(session_error: bool = False):
    def _generate_fake_lgnetcast_client(*args, **kwargs):
        return _patched_lgnetcast_client(*args, session_error=session_error, **kwargs)

    return patch(
        "homeassistant.components.lg_netcast.config_flow.LgNetCastClient",
        new=_generate_fake_lgnetcast_client,
    )
