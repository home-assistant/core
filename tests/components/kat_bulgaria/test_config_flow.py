"""Test KAT Bulgaria setup process."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.kat_bulgaria import const as kat_constants
from homeassistant.components.kat_bulgaria.const import (
    CONF_DRIVING_LICENSE,
    CONF_PERSON_EGN,
    CONF_PERSON_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    EGN_INVALID,
    EGN_VALID,
    LICENSE_INVALID,
    LICENSE_VALID,
    MOCK_DATA,
    MOCK_NAME,
)

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_flow_works(
    hass: HomeAssistant, validate_credentials: pytest.fixture
) -> None:
    """Test config flow."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.CREATE_ENTRY
    assert config_result["title"] == MOCK_NAME
    assert config_result["data"] == MOCK_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_details_error(
    hass: HomeAssistant, validate_credentials_error_notfoundonline
) -> None:
    """Test config flow when user is not found online."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    config_result = await hass.config_entries.flow.async_configure(
        flow_result["flow_id"], user_input=MOCK_DATA
    )
    await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "invalid_config"}


async def test_invalid_egn(hass: HomeAssistant, validate_credentials_error_egn) -> None:
    """Test host already configured."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    MOCK_DATA_INVALID = {
        CONF_PERSON_NAME: "test",
        CONF_PERSON_EGN: EGN_INVALID,
        CONF_DRIVING_LICENSE: LICENSE_VALID,
    }
    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA_INVALID,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "invalid_config"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_invalid_license(
    hass: HomeAssistant, validate_credentials_error_license
) -> None:
    """Test host already configured."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    MOCK_DATA_INVALID = {
        CONF_PERSON_NAME: "test",
        CONF_PERSON_EGN: EGN_VALID,
        CONF_DRIVING_LICENSE: LICENSE_INVALID,
    }
    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA_INVALID,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "invalid_config"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_host_already_configured(
    hass: HomeAssistant, validate_credentials
) -> None:
    """Test host already configured."""

    entry = MockConfigEntry(
        domain=kat_constants.DOMAIN,
        data=MOCK_DATA,
        unique_id=EGN_VALID,
    )
    entry.add_to_hass(hass)

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ):
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"], user_input=MOCK_DATA
        )

    assert config_result["type"] is FlowResultType.ABORT
    assert config_result["reason"] == "already_configured"


async def test_api_timeout(
    hass: HomeAssistant, validate_credentials_api_timeout
) -> None:
    """Test API timeout."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_api_errorreadingdata(
    hass: HomeAssistant, validate_credentials_api_errorreadingdata
) -> None:
    """Test herror reading data from API."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_api_invalidschema(
    hass: HomeAssistant, validate_credentials_api_invalidschema
) -> None:
    """Test invalid data schema."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_api_toomanyrequests(
    hass: HomeAssistant, validate_credentials_api_toomanyrequests
) -> None:
    """Test too many requests API error."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_api_unknownerror(
    hass: HomeAssistant, validate_credentials_api_unknownerror
) -> None:
    """Test unknown error."""

    flow_result = await hass.config_entries.flow.async_init(
        kat_constants.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    with patch(
        "homeassistant.components.kat_bulgaria.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=MOCK_DATA,
        )
        await hass.async_block_till_done()

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0
