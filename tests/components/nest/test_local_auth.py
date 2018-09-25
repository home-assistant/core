"""Test Nest local auth."""
from homeassistant.components.nest import const, config_flow, local_auth
from urllib.parse import parse_qsl

import pytest

import requests_mock as rmock


@pytest.fixture
def registered_flow(hass):
    """Mock a registered flow."""
    local_auth.initialize(hass, 'TEST-CLIENT-ID', 'TEST-CLIENT-SECRET')
    return hass.data[config_flow.DATA_FLOW_IMPL][const.DOMAIN]


async def test_generate_auth_url(registered_flow):
    """Test generating an auth url.

    Mainly testing that it doesn't blow up.
    """
    url = await registered_flow['gen_authorize_url']('TEST-FLOW-ID')
    assert url is not None


async def test_convert_code(requests_mock, registered_flow):
    """Test converting a code."""
    from nest.nest import ACCESS_TOKEN_URL

    def token_matcher(request):
        """Match a fetch token request."""
        if request.url != ACCESS_TOKEN_URL:
            return None

        assert dict(parse_qsl(request.text)) == {
            'client_id': 'TEST-CLIENT-ID',
            'client_secret': 'TEST-CLIENT-SECRET',
            'code': 'TEST-CODE',
            'grant_type': 'authorization_code'
        }

        return rmock.create_response(request, json={
            'access_token': 'TEST-ACCESS-TOKEN'
        })

    requests_mock.add_matcher(token_matcher)

    tokens = await registered_flow['convert_code']('TEST-CODE')
    assert tokens == {
        'access_token': 'TEST-ACCESS-TOKEN'
    }
