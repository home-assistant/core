"""Define tests for the AEMET OpenData config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aemet_opendata.exceptions import AuthError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aemet.const import (
    CONF_API_KEY_DATE,
    CONF_API_KEY_REMINDER,
    CONF_RADAR_UPDATES,
    CONF_STATION_UPDATES,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .util import mock_api_call

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

CONFIG = {
    CONF_API_KEY: "foo",
    CONF_LOCATION: {
        CONF_LATITUDE: 40.30403754,
        CONF_LONGITUDE: -3.72935236,
    },
}


async def test_form(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that the form is served with valid input."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LOCATION][CONF_LATITUDE]
        assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LOCATION][CONF_LONGITUDE]
        assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
        assert result["data"][CONF_API_KEY_DATE] == "2021-01-09"
        assert entry.options[CONF_API_KEY_REMINDER] is False
        assert result["result"].unique_id == "40.30403754--3.72935236"

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        (
            {},
            {
                CONF_API_KEY_REMINDER: False,
                CONF_RADAR_UPDATES: False,
                CONF_STATION_UPDATES: True,
            },
        ),
        (
            {
                CONF_API_KEY_REMINDER: True,
                CONF_RADAR_UPDATES: False,
                CONF_STATION_UPDATES: False,
            },
            {
                CONF_API_KEY_REMINDER: True,
                CONF_RADAR_UPDATES: False,
                CONF_STATION_UPDATES: False,
            },
        ),
    ],
)
async def test_form_options(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    user_input: dict[str, bool],
    expected: dict[str, bool],
) -> None:
    """Test the form options."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN, unique_id="40.30403754--3.72935236", data=CONFIG
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=user_input
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options == {
            CONF_API_KEY_REMINDER: expected[CONF_API_KEY_REMINDER],
            CONF_RADAR_UPDATES: expected[CONF_RADAR_UPDATES],
            CONF_STATION_UPDATES: expected[CONF_STATION_UPDATES],
        }

        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED


async def test_form_duplicated_id(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting up duplicated entry."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN, unique_id="40.30403754--3.72935236", data=CONFIG
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_form_auth_error(hass: HomeAssistant) -> None:
    """Test setting up with api auth error."""
    mocked_aemet = MagicMock()
    mocked_aemet.select_coordinates.side_effect = AuthError

    with patch(
        "homeassistant.components.aemet.config_flow.AEMET",
        return_value=mocked_aemet,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG,
        )

        assert result["errors"] == {"base": "invalid_api_key"}

        mocked_aemet.select_coordinates = AsyncMock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_with_reminder_and_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the API key date and reminder are stored."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    user_input = {
        **CONFIG,
        CONF_API_KEY_DATE: "2021-01-01",
        CONF_API_KEY_REMINDER: True,
    }

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY_DATE] == "2021-01-01"
    assert entry.options[CONF_API_KEY_REMINDER] is True
    assert result["result"].unique_id == "40.30403754--3.72935236"


async def test_form_invalid_future_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a future API key generation date is rejected."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**CONFIG, CONF_API_KEY_DATE: "2021-01-10"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_API_KEY_DATE: "invalid_date"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**CONFIG, CONF_API_KEY_DATE: "2021-01-09"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY_DATE] == "2021-01-09"
    assert result["result"].unique_id == "40.30403754--3.72935236"


@pytest.mark.parametrize(
    ("date_input", "expected_date"),
    [
        (None, "2021-02-01"),
        ("2021-01-15", "2021-01-15"),
    ],
)
@pytest.mark.parametrize("reminder_enabled", [False, True])
async def test_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    date_input: str | None,
    expected_date: str,
    reminder_enabled: bool,
) -> None:
    """Test reauthentication updates the API key and date."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-02-01 12:00:00+00:00")

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="40.30403754--3.72935236",
        data={
            CONF_API_KEY: "foo",
            CONF_API_KEY_DATE: "2021-01-01",
            CONF_LATITUDE: 40.30403754,
            CONF_LONGITUDE: -3.72935236,
        },
        options={CONF_API_KEY_REMINDER: reminder_enabled},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mocked_aemet = MagicMock()
    mocked_aemet.select_coordinates = AsyncMock()

    with patch(
        "homeassistant.components.aemet.config_flow.AEMET",
        return_value=mocked_aemet,
    ):
        result = await entry.start_reauth_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        user_input = {CONF_API_KEY: "new-key"}
        if date_input is not None:
            user_input[CONF_API_KEY_DATE] = date_input
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"
    assert entry.data[CONF_API_KEY_DATE] == expected_date
    assert entry.options == {CONF_API_KEY_REMINDER: reminder_enabled}
    assert entry.state is ConfigEntryState.LOADED


async def test_reauth_invalid_future_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauthentication rejects a future API key generation date."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-02-01 12:00:00+00:00")

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="40.30403754--3.72935236",
        data={
            CONF_API_KEY: "foo",
            CONF_API_KEY_DATE: "2021-01-01",
            CONF_LATITUDE: 40.30403754,
            CONF_LONGITUDE: -3.72935236,
        },
        options={CONF_API_KEY_REMINDER: True},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mocked_aemet = MagicMock()
    mocked_aemet.select_coordinates = AsyncMock()

    with patch(
        "homeassistant.components.aemet.config_flow.AEMET",
        return_value=mocked_aemet,
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "new-key",
                CONF_API_KEY_DATE: "2021-02-02",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_API_KEY_DATE: "invalid_date"}
        assert entry.data[CONF_API_KEY] == "foo"
        assert entry.data[CONF_API_KEY_DATE] == "2021-01-01"
        assert entry.options == {CONF_API_KEY_REMINDER: True}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "new-key",
                CONF_API_KEY_DATE: "2021-02-01",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"
    assert entry.data[CONF_API_KEY_DATE] == "2021-02-01"
    assert entry.options == {CONF_API_KEY_REMINDER: True}
