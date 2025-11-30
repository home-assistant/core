"""Test the Diyanet config flow (multi-step country/state/city)."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.diyanet.api import (
    DiyanetAuthError,
    DiyanetConnectionError,
)
from homeassistant.components.diyanet.const import CONF_LOCATION_ID, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test happy path through user -> country -> state -> city -> create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    # Submit credentials; entering select_country builds schema from API
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_countries",
            return_value=[
                {"id": 2, "code": "TURKIYE", "name": "Türkiye"},
                {"id": 4, "code": "NETHERLANDS", "name": "Hollanda"},
            ],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "secret",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_country"

    # Select country (patch lists while submitting to avoid auth)
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_countries",
            return_value=[
                {"id": 2, "code": "TURKIYE", "name": "Türkiye"},
                {"id": 4, "code": "NETHERLANDS", "name": "Hollanda"},
            ],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_states",
            return_value=[
                {"id": 34, "code": "ISTANBUL", "name": "İstanbul"},
                {"id": 35, "code": "IZMIR", "name": "İzmir"},
            ],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
            return_value=[
                {"id": 13975, "code": "ISTANBUL", "name": "İstanbul"},
                {"id": 14000, "code": "KADIKOY", "name": "Kadıköy"},
            ],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"country_id": "2"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_state"

    # Enter select_state (schema built now)
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_states",
            return_value=[
                {"id": 34, "code": "ISTANBUL", "name": "İstanbul"},
                {"id": 35, "code": "IZMIR", "name": "İzmir"},
            ],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
            return_value=[
                {"id": 13975, "code": "ISTANBUL", "name": "İstanbul"},
                {"id": 14000, "code": "KADIKOY", "name": "Kadıköy"},
            ],
        ),
    ):
        # Show state selection form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_state"
        # Submit selected state (patch cities during submit)
        with (
            patch(
                "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
                return_value=None,
            ),
            patch(
                "homeassistant.components.diyanet.api.DiyanetApiClient.get_states",
                return_value=[
                    {"id": 34, "code": "ISTANBUL", "name": "İstanbul"},
                    {"id": 35, "code": "IZMIR", "name": "İzmir"},
                ],
            ),
            patch(
                "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
                return_value=[
                    {"id": 13975, "code": "ISTANBUL", "name": "İstanbul"},
                    {"id": 14000, "code": "KADIKOY", "name": "Kadıköy"},
                ],
            ),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"state_id": "34"}
            )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_city"

    # Enter select_city (schema built now) and finish
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
            return_value=[
                {"id": 13975, "code": "ISTANBUL", "name": "İstanbul"},
                {"id": 14000, "code": "KADIKOY", "name": "Kadıköy"},
            ],
        ),
    ):
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_city"
        with patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_prayer_times",
            return_value={"gregorianDateLong": "01 January 2025"},
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"city_id": "13975"}
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Diyanet (ISTANBUL – İstanbul, ISTANBUL, TURKIYE)"
    assert result["data"] == {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_LOCATION_ID: 13975,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Abort if an entry with the same unique_id (email) already exists."""
    # Existing entry with same unique_id (email lowered)
    existing = MockConfigEntry(
        title="Diyanet",
        domain=DOMAIN,
        data={},
        unique_id="user@example.com",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Authenticate ok; we abort on unique_id
    with patch(
        "homeassistant.components.diyanet.api.DiyanetApiClient.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.diyanet.api.DiyanetApiClient.authenticate",
        side_effect=DiyanetAuthError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    # Recover: go through full flow
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_countries",
            return_value=[{"id": 2, "code": "TURKIYE", "name": "Türkiye"}],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
        )
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_countries",
            return_value=[{"id": 2, "code": "TURKIYE", "name": "Türkiye"}],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_states",
            return_value=[{"id": 34, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"country_id": "2"}
        )
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_states",
            return_value=[{"id": 34, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
            return_value=[{"id": 13975, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
    ):
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_state"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"state_id": "34"}
        )
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
            return_value=[{"id": 13975, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_prayer_times",
            return_value={"gregorianDateLong": "01 January 2025"},
        ),
    ):
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_city"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"city_id": "13975"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Diyanet (ISTANBUL – İstanbul, ISTANBUL, TURKIYE)"
    assert result["data"] == {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_LOCATION_ID: 13975,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.diyanet.api.DiyanetApiClient.authenticate",
        side_effect=DiyanetConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    # Recover: proceed through country/state/city
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_countries",
            return_value=[{"id": 2, "code": "TURKIYE", "name": "Türkiye"}],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
        )
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_countries",
            return_value=[{"id": 2, "code": "TURKIYE", "name": "Türkiye"}],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_states",
            return_value=[{"id": 34, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"country_id": "2"}
        )
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_states",
            return_value=[{"id": 34, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
            return_value=[{"id": 13975, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
    ):
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_state"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"state_id": "34"}
        )
    with (
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient._ensure_authenticated",
            return_value=None,
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_cities",
            return_value=[{"id": 13975, "code": "ISTANBUL", "name": "İstanbul"}],
        ),
        patch(
            "homeassistant.components.diyanet.api.DiyanetApiClient.get_prayer_times",
            return_value={"gregorianDateLong": "01 January 2025"},
        ),
    ):
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_city"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"city_id": "13975"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Diyanet (ISTANBUL – İstanbul, ISTANBUL, TURKIYE)"
    assert result["data"] == {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_LOCATION_ID: 13975,
    }
    assert len(mock_setup_entry.mock_calls) == 1
