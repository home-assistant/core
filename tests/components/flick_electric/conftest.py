"""Flick Electric tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import json_api_doc
from pyflick import FlickPrice
import pytest

from homeassistant.components.flick_electric.const import (
    CONF_ACCOUNT_ID,
    CONF_SUPPLY_NODE_REF,
    DOMAIN,
)
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry, load_json_value_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="123 Fake Street, Newtown, Wellington 6021",
        data={
            CONF_USERNAME: "9973debf-963f-49b0-9a73-ba9c3400cbed@anonymised.example.com",
            CONF_PASSWORD: "test-password",
            CONF_ACCOUNT_ID: "10123404",
            CONF_SUPPLY_NODE_REF: "/network/nz/supply_nodes/ed7617df-4b10-4c8a-a05d-deadbeef8299",
            CONF_CLIENT_ID: "test-client-id",
            CONF_CLIENT_SECRET: "test-client-secret",
        },
        version=2,
        entry_id="974e52a5c0724d17b7ed876dd6ff4bc8",
        unique_id="10123404",
    )


@pytest.fixture
def mock_flick_client() -> Generator[AsyncMock]:
    """Mock an Overseerr client."""
    with (
        patch(
            "homeassistant.components.flick_electric.FlickAPI",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI",
            new=mock_api,
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
