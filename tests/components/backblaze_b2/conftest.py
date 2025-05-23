"""Common fixtures for the Backblaze B2 tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from b2sdk.v2 import RawSimulator
import pytest

from homeassistant.components.backblaze_b2.const import (
    CONF_APPLICATION_KEY,
    CONF_BUCKET,
    CONF_KEY_ID,
    DOMAIN,
)

from .const import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.backblaze_b2.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def b2_fixture():
    """Create account and application keys."""
    sim = RawSimulator()
    with (
        patch("b2sdk.v2.B2Api", return_value=sim) as mock_client,
        patch("homeassistant.components.backblaze_b2.B2Api", return_value=sim),
    ):
        RawSimulator.get_bucket_by_name = RawSimulator._get_bucket_by_name

        allowed = {
            "capabilities": [
                "writeFiles",
                "listFiles",
                "deleteFiles",
                "readFiles",
            ]
        }
        RawSimulator.account_info = AccountInfo(allowed)

        sim: RawSimulator = mock_client.return_value
        account_id, application_key = sim.create_account()
        auth = sim.authorize_account("production", account_id, application_key)
        auth_token: str = auth["authorizationToken"]
        api_url: str = auth["apiInfo"]["storageApi"]["apiUrl"]

        key = sim.create_key(
            api_url=api_url,
            account_auth_token=auth_token,
            account_id=account_id,
            key_name="testkey",
            capabilities=[
                "writeFiles",
                "listFiles",
                "deleteFiles",
                "readFiles",
            ],
            valid_duration_seconds=None,
            bucket_id=None,
            name_prefix=None,
        )

        application_key_id: str = key["applicationKeyId"]
        application_key: str = key["applicationKey"]

        bucket = sim.create_bucket(
            api_url=api_url,
            account_id=account_id,
            account_auth_token=auth_token,
            bucket_name=USER_INPUT[CONF_BUCKET],
            bucket_type="allPrivate",
        )

        yield BackblazeFixture(application_key_id, application_key, bucket, sim, auth)


@pytest.fixture
def mock_config_entry(b2_fixture: Any) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="test",
        title="test",
        domain=DOMAIN,
        data={
            **USER_INPUT,
            CONF_KEY_ID: b2_fixture.key_id,
            CONF_APPLICATION_KEY: b2_fixture.application_key,
        },
    )


class BackblazeFixture:
    """Mock Backblaze B2 account."""

    def __init__(  # noqa: D107
        self,
        key_id: str,
        application_key: str,
        bucket: dict[str, Any],
        sim: RawSimulator,
        auth: dict[str, Any],
    ) -> None:
        self.key_id = key_id
        self.application_key = application_key
        self.bucket = bucket
        self.sim = sim
        self.auth = auth
        self.api_url = auth["apiInfo"]["storageApi"]["apiUrl"]
        self.account_id = auth["accountId"]


class AccountInfo:
    """Mock account info."""

    def __init__(self, allowed: dict[str, Any]) -> None:  # noqa: D107
        self._allowed = allowed

    def get_allowed(self):
        """Return allowed capabilities."""
        return self._allowed
