"""Flick Electric tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import json_api_doc
from pyflick import FlickPrice
import pytest

from homeassistant.components.flick_electric.const import CONF_ACCOUNT_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from . import CONF

from tests.common import MockConfigEntry, load_json_value_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="123 Fake Street, Newtown, Wellington 6021",
        data={**CONF},
        version=2,
        entry_id="974e52a5c0724d17b7ed876dd6ff4bc8",
        unique_id=CONF[CONF_ACCOUNT_ID],
    )


@pytest.fixture
def mock_old_config_entry() -> MockConfigEntry:
    """Mock an outdated config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
        title=CONF[CONF_USERNAME],
        unique_id=CONF[CONF_USERNAME],
        version=1,
    )


@pytest.fixture
def mock_flick_client() -> Generator[AsyncMock]:
    """Mock a Flick Electric client."""
    with (
        patch(
            "homeassistant.components.flick_electric.FlickAPI",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI",
            new=mock_api,
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
    ):
        api = mock_api.return_value

        api.getCustomerAccounts.return_value = json_api_doc.deserialize(
            load_json_value_fixture("accounts.json", DOMAIN)
        )
        api.getPricing.return_value = FlickPrice(
            json_api_doc.deserialize(
                load_json_value_fixture("rated_period.json", DOMAIN)
            )
        )

        yield api


@pytest.fixture
def mock_flick_client_multiple() -> Generator[AsyncMock]:
    """Mock a Flick Electric with multiple accounts."""
    with (
        patch(
            "homeassistant.components.flick_electric.FlickAPI",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI",
            new=mock_api,
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
    ):
        api = mock_api.return_value

        api.getCustomerAccounts.return_value = json_api_doc.deserialize(
            load_json_value_fixture("accounts_multi.json", DOMAIN)
        )
        api.getPricing.return_value = FlickPrice(
            json_api_doc.deserialize(
                load_json_value_fixture("rated_period.json", DOMAIN)
            )
        )

        yield api
