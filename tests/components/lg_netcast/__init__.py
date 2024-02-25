"""Tests for LG Netcast TV."""
from unittest.mock import patch

from pylgnetcast import AccessTokenError, LgNetCastClient, SessionIdError
import requests
import requests_mock

from tests.common import load_fixture

FAIL_TO_BIND_IP = "1.2.3.4"

IP_ADDRESS = "192.168.1.239"
DEVICE_TYPE = "TV"
MODEL_NAME = "MockLGModelName"
FRIENDLY_NAME = "LG Smart TV"
UNIQUE_ID = "1234"

FAKE_SESSION_ID = "987654321"
FAKE_PIN = "123456"


def _patched_lgnetcast_client(
    *args,
    session_error=False,
    fail_connection: bool = True,
    invalid_details: bool = False,
    always_404: bool = False,
    no_unique_id: bool = False,
    **kwargs,
):
    client = LgNetCastClient(*args, **kwargs)

    def _get_fake_session_id():
        if not client.access_token:
            raise AccessTokenError("Fake Access Token Requested")
        if session_error:
            raise SessionIdError("Can not get session id from TV.")
        return FAKE_SESSION_ID

    def _send_fake_to_tv_wrapper(func):
        def _send_fake_to_tv(*args, **kwargs):
            with requests_mock.Mocker() as m:
                if fail_connection:
                    m.get(
                        f"{client.url}data?target=rootservice.xml",
                        exc=requests.exceptions.ConnectTimeout,
                    )
                elif invalid_details:
                    m.get(
                        f"{client.url}data?target=rootservice.xml",
                        text=load_fixture("invalid_rootservice.xml", "lg_netcast"),
                    )
                elif no_unique_id:
                    m.get(
                        f"{client.url}data?target=rootservice.xml",
                        request_headers={"User-Agent": "UDAP/2.0"},
                        text=load_fixture("rootservice_no_unique_id.xml", "lg_netcast"),
                        status_code=200,
                    )
                else:
                    m.get(
                        f"{client.url}data?target=rootservice.xml",
                        text=load_fixture(
                            "invalid_useragent_rootservice.xml", "lg_netcast"
                        ),
                        status_code=404,
                    )
                    if not always_404:
                        m.get(
                            f"{client.url}data?target=rootservice.xml",
                            request_headers={"User-Agent": "UDAP/2.0"},
                            text=load_fixture("rootservice.xml", "lg_netcast"),
                            status_code=200,
                        )
                return func(*args, **kwargs)

        return _send_fake_to_tv

    client._get_session_id = _get_fake_session_id
    client._send_to_tv = _send_fake_to_tv_wrapper(client._send_to_tv)

    return client


def _patch_lg_netcast(
    *,
    session_error: bool = False,
    fail_connection: bool = False,
    invalid_details: bool = False,
    always_404: bool = False,
    no_unique_id: bool = False,
):
    def _generate_fake_lgnetcast_client(*args, **kwargs):
        return _patched_lgnetcast_client(
            *args,
            session_error=session_error,
            fail_connection=fail_connection,
            invalid_details=invalid_details,
            always_404=always_404,
            no_unique_id=no_unique_id,
            **kwargs,
        )

    return patch(
        "homeassistant.components.lg_netcast.config_flow.LgNetCastClient",
        new=_generate_fake_lgnetcast_client,
    )
