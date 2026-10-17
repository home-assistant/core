"""Shared synthetic OAuth helpers for NuHeat tests."""

import base64
import json
from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


def jwt_access_token(
    subject: str | None = "synthetic-account-subject", *, marker: str | None = None
) -> str:
    """Create a clearly synthetic unsigned JWT for identity-claim tests."""

    def encode(value: dict[str, str]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    payload: dict[str, str] = {}
    if subject is not None:
        payload["sub"] = subject
    if marker is not None:
        payload["test_marker"] = marker
    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode(payload)}.synthetic"


class FakeOAuthImplementation(AbstractOAuth2Implementation):
    """Synthetic OAuth implementation used through the real flow manager."""

    def __init__(
        self,
        *,
        token: dict[str, Any] | None = None,
        domain: str = "test",
    ) -> None:
        """Initialize the implementation with a clearly fake token response."""
        self._token = token or {
            "access_token": jwt_access_token(),
            "refresh_token": "synthetic-refresh-token",
            "expires_in": 3600,
        }
        self._domain = domain

    @property
    def name(self) -> str:
        """Return the implementation name."""
        return "Synthetic test credentials"

    @property
    def domain(self) -> str:
        """Return the implementation domain."""
        return self._domain

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Return a synthetic authorization URL."""
        return "https://identity.example/authorize"

    async def async_resolve_external_data(self, external_data: object) -> dict:
        """Resolve the synthetic callback into the configured token response."""
        return dict(self._token)

    async def _async_refresh_token(self, token: dict) -> dict:
        return {
            **token,
            "access_token": "rotated-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 3600,
        }


async def complete_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    implementation: FakeOAuthImplementation,
    *,
    entry: MockConfigEntry | None = None,
    confirmation_step: str | None = None,
) -> config_entries.ConfigFlowResult:
    """Complete user setup or reauthentication through the public flow manager."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_implementations",
        return_value={implementation.domain: implementation},
    ):
        if entry is None:
            result = await hass.config_entries.flow.async_init(
                "nuheat", context={"source": config_entries.SOURCE_USER}
            )
        else:
            result = await entry.start_reauth_flow(hass)

        if confirmation_step is not None:
            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == confirmation_step
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {}
            )

        if result["type"] is FlowResultType.FORM:
            assert result["step_id"] == "pick_implementation"
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"implementation": implementation.domain}
            )

        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"
        state = config_entry_oauth2_flow._encode_jwt(
            hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": "https://example.com/auth/external/callback",
            },
        )
        client = await hass_client_no_auth()
        response = await client.get(
            f"/auth/external/callback?code=synthetic-authorization-code&state={state}"
        )
        assert response.status == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        return await hass.config_entries.flow.async_configure(result["flow_id"])
