"""Test Google http services."""
from asynctest import patch, ANY
from datetime import datetime

from homeassistant.components.google_assistant.http import GoogleConfig
from homeassistant.components.google_assistant import GOOGLE_ASSISTANT_SCHEMA
from homeassistant.components.google_assistant.const import (
    REPORT_STATE_BASE_URL,
    HOMEGRAPH_AUDIENCE,
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
    config = GoogleConfig(hass, DUMMY_CONFIG)

    with patch("homeassistant.components.google_assistant.http.dt_util") as mock_dt:
        mock_dt.utcnow.return_value = datetime(2019, 10, 14)
        jwt = config._async_get_jwt()
        assert jwt == (
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJkdW1teUBkdW1teS5pYW0uZ3NlcnZ"
            "pY2VhY2NvdW50LmNvbSIsInNjb3BlIjoiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9"
            "ob21lZ3JhcGgiLCJhdWQiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0aDIvdG9"
            "rZW4iLCJpc3QiOjE1NzEwMDQwMDAuMCwiZXhwIjoxNTcxMDA3NjAwLjB9.J64gpWBonUUs9S71ty"
            "bQ0VlStodPBtiejIKH0LOIjYE"
        )


async def test_get_access_token(hass, aioclient_mock):
    """Test the function to get access token."""

    # TODO this should be cached with expire time remembered

    config = GoogleConfig(hass, DUMMY_CONFIG)
    with patch.object(config, "_async_get_jwt") as mock_get_token:

        token = "dummyjwt"
        mock_get_token.return_value = token

        aioclient_mock.post(HOMEGRAPH_AUDIENCE, status=200)

        await config._async_get_access_token()
        assert aioclient_mock.call_count == 1
        assert aioclient_mock.mock_calls[0][3] == {
            "Authorization": "Bearer {}".format(token)
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

        aioclient_mock.post(REPORT_STATE_BASE_URL, status=200)

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
