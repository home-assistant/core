"""Test Google http services."""
from asynctest import patch, ANY
from datetime import datetime

from homeassistant.components.google_assistant.http import (
    GoogleConfig,
    _get_homegraph_jwt,
)
from homeassistant.components.google_assistant import GOOGLE_ASSISTANT_SCHEMA
from homeassistant.components.google_assistant.const import (
    REPORT_STATE_BASE_URL,
    HOMEGRAPH_TOKEN_URL,
)
from homeassistant.auth.models import User

DUMMY_CONFIG = GOOGLE_ASSISTANT_SCHEMA(
    {
        "project_id": "1234",
        "service_account": {
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAKYscIlwm7soDsHAz6L6YvUkCvkrX19rS6yeYOmovvhoK5WeYGWUsd8V72zmsyHB7XO94YgJVjvxfzn5K8bLePjFzwoSJjZvhBJ/ZQ05d8VmbvgyWUoPdG9oEa4fZ/lCYrXoaFdTot2xcJvrb/ZuiRl4s4eZpNeFYvVK/Am7UeFPAgMBAAECgYAUetOfzLYUudofvPCaKHu7tKZ5kQPfEa0w6BAPnBF1Mfl1JiDBRDMryFtKs6AOIAVwx00dY/Ex0BCbB3+Cr58H7t4NaPTJxCpmR09pK7o17B7xAdQv8+SynFNud9/5vQ5AEXMOLNwKiU7wpXT6Z7ZIibUBOR7ewsWgsHCDpN1iqQJBAOMODPTPSiQMwRAUHIc6GPleFSJnIz2PAoG3JOG9KFAL6RtIc19lob2ZXdbQdzKtjSkWo+O5W20WDNAl1k32h6MCQQC7W4ZCIY67mPbL6CxXfHjpSGF4Dr9VWJ7ZrKHr6XUoOIcEvsn/pHvWonjMdy93rQMSfOE8BKd/I1+GHRmNVgplAkAnSo4paxmsZVyfeKt7Jy2dMY+8tVZe17maUuQaAE7Sk00SgJYegwrbMYgQnWCTL39HBfj0dmYA2Zj8CCAuu6O7AkEAryFiYjaUAO9+4iNoL27+ZrFtypeeadyov7gKs0ZKaQpNyzW8A+Zwi7TbTeSqzic/E+z/bOa82q7p/6b7141xsQJBANCAcIwMcVb6KVCHlQbOtKspo5Eh4ZQi8bGl+IcwbQ6JSxeTx915IfAldgbuU047wOB04dYCFB2yLDiUGVXTifU=\n-----END PRIVATE KEY-----\n",
            "client_email": "dummy@dummy.iam.gserviceaccount.com",
        },
    }
)


async def test_get_jwt(hass):
    """Test signing of key."""

    key = "-----BEGIN PRIVATE KEY-----\nMIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAKYscIlwm7soDsHAz6L6YvUkCvkrX19rS6yeYOmovvhoK5WeYGWUsd8V72zmsyHB7XO94YgJVjvxfzn5K8bLePjFzwoSJjZvhBJ/ZQ05d8VmbvgyWUoPdG9oEa4fZ/lCYrXoaFdTot2xcJvrb/ZuiRl4s4eZpNeFYvVK/Am7UeFPAgMBAAECgYAUetOfzLYUudofvPCaKHu7tKZ5kQPfEa0w6BAPnBF1Mfl1JiDBRDMryFtKs6AOIAVwx00dY/Ex0BCbB3+Cr58H7t4NaPTJxCpmR09pK7o17B7xAdQv8+SynFNud9/5vQ5AEXMOLNwKiU7wpXT6Z7ZIibUBOR7ewsWgsHCDpN1iqQJBAOMODPTPSiQMwRAUHIc6GPleFSJnIz2PAoG3JOG9KFAL6RtIc19lob2ZXdbQdzKtjSkWo+O5W20WDNAl1k32h6MCQQC7W4ZCIY67mPbL6CxXfHjpSGF4Dr9VWJ7ZrKHr6XUoOIcEvsn/pHvWonjMdy93rQMSfOE8BKd/I1+GHRmNVgplAkAnSo4paxmsZVyfeKt7Jy2dMY+8tVZe17maUuQaAE7Sk00SgJYegwrbMYgQnWCTL39HBfj0dmYA2Zj8CCAuu6O7AkEAryFiYjaUAO9+4iNoL27+ZrFtypeeadyov7gKs0ZKaQpNyzW8A+Zwi7TbTeSqzic/E+z/bOa82q7p/6b7141xsQJBANCAcIwMcVb6KVCHlQbOtKspo5Eh4ZQi8bGl+IcwbQ6JSxeTx915IfAldgbuU047wOB04dYCFB2yLDiUGVXTifU=\n-----END PRIVATE KEY-----\n"
    jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJkdW1teUBkdW1teS5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsInNjb3BlIjoiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9ob21lZ3JhcGgiLCJhdWQiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0aDIvdG9rZW4iLCJpYXQiOjE1NzEwMDQwMDAsImV4cCI6MTU3MTAwNzYwMH0.V4mXq5_GflIeg176axybOCmbrqMtx37vi4l5asoK35y9cRcDO51y4rRrrVzhmVQTLJk4GgpIfshS5Z0YJO2L8XP9njp2ql9O98bUy3wKQuprVefnXuPmTFlUUCOKsgUNhrr5-TkjCjo9mDJ13wKBpslCtp9w2T0IGsaNdm-dc3g"
    res = _get_homegraph_jwt(
        datetime(2019, 10, 14), "dummy@dummy.iam.gserviceaccount.com", key
    )
    assert res == jwt


async def test_get_access_token(hass, aioclient_mock):
    """Test the function to get access token."""

    # TODO this should be cached with expire time remembered

    config = GoogleConfig(hass, DUMMY_CONFIG)
    with patch(
        "homeassistant.components.google_assistant.http._get_homegraph_jwt"
    ) as mock_get_token:

        now = datetime(2019, 10, 14)
        token = "dummyjwt"
        mock_get_token.return_value = token

        aioclient_mock.post(
            HOMEGRAPH_TOKEN_URL,
            status=200,
            json={"access_token": "1234", "expires_in": 3600},
        )

        await config._async_get_access_token(now)
        assert aioclient_mock.call_count == 1
        assert aioclient_mock.mock_calls[0][3] == {
            "Authorization": "Bearer {}".format(token),
            "Content-Type": "application/x-www-form-urlencoded",
        }


async def test_report_state(hass, aioclient_mock, hass_storage):
    """Test the report state function."""
    config = GoogleConfig(hass, DUMMY_CONFIG)
    with patch.object(
        config, "_async_get_access_token"
    ) as mock_get_token, patch.object(hass.auth, "async_get_owner") as mock_get_owner:

        token = "dummyaccess"
        message = {"devices": {}}
        mock_get_token.return_value = token
        owner = User(name="Test User", perm_lookup=None, groups=[], is_owner=True)
        mock_get_owner.return_value = owner

        aioclient_mock.post(REPORT_STATE_BASE_URL, status=200, json={})

        await config.async_report_state(message)

        assert aioclient_mock.call_count == 1
        call = aioclient_mock.mock_calls[0]
        assert call[3] == {
            "Authorization": "Bearer {}".format(token),
            "X-GFE-SSL": "yes",
        }
        assert call[2] == {
            "requestId": ANY,
            "agentUserId": owner.id,
            "payload": message,
        }
