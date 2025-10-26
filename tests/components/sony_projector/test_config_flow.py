"""Tests for the Sony Projector config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sony_projector.config_flow import ProjectorClientError
from homeassistant.components.sony_projector.const import CONF_TITLE, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_projector_client_validate", autouse=True)
def mock_projector_client_validate_fixture() -> AsyncMock:
    """Mock the projector client validation call."""

    with patch(
        "homeassistant.components.sony_projector.config_flow.ProjectorClient.async_validate_connection",
        new_callable=AsyncMock,
    ) as mock_validate:
        mock_validate.return_value = None
        yield mock_validate


@pytest.fixture(autouse=True)
def ignore_sony_projector_translations(
    ignore_missing_translations: list[str],
) -> list[str]:
    """Ignore translation checks that rely on the localized pipeline."""

    ignore_missing_translations.extend(
        [
            "config.error.cannot_connect",
            "config.abort.cannot_connect",
            "config.abort.already_configured",
        ]
    )
    return ignore_missing_translations


@pytest.fixture(autouse=True)
def ignore_mock_domain_translations(
    ignore_translations_for_mock_domains: list[str],
) -> list[str]:
    """Skip translation validation for the mocked sony_projector domain."""

    ignore_translations_for_mock_domains.append(DOMAIN)
    return ignore_translations_for_mock_domains


@pytest.fixture(name="check_translations", autouse=True)
async def check_translations_fixture() -> None:
    """Disable the global translation checks for this module."""

    return


def _start_user_flow(hass: HomeAssistant):
    return hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )


async def test_user_step_success(
    hass: HomeAssistant, mock_projector_client_validate: AsyncMock
) -> None:
    """Test a successful user initiated flow."""

    result = await _start_user_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    mock_projector_client_validate.reset_mock()
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_NAME: "Theater"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Theater"
    assert result2["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_TITLE: "Theater",
    }
    mock_projector_client_validate.assert_awaited_once_with()


async def test_user_step_defaults_title_when_name_missing(
    hass: HomeAssistant, mock_projector_client_validate: AsyncMock
) -> None:
    """Test that the default title is used when the name is omitted."""

    result = await _start_user_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "4.5.6.7"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sony Projector"
    assert result2["data"] == {
        CONF_HOST: "4.5.6.7",
        CONF_TITLE: "Sony Projector",
    }


async def test_user_step_cannot_connect(
    hass: HomeAssistant, mock_projector_client_validate: AsyncMock
) -> None:
    """Test handling when the projector cannot be reached."""

    mock_projector_client_validate.side_effect = ProjectorClientError

    result = await _start_user_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import_step_success(
    hass: HomeAssistant, mock_projector_client_validate: AsyncMock
) -> None:
    """Test importing configuration from YAML."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: "Main"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Main"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_TITLE: "Main",
    }
    mock_projector_client_validate.assert_awaited_once_with()


async def test_import_step_cannot_connect(
    hass: HomeAssistant, mock_projector_client_validate: AsyncMock
) -> None:
    """Test aborting the import when the projector is unreachable."""

    mock_projector_client_validate.side_effect = ProjectorClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_aborts_when_projector_already_configured(
    hass: HomeAssistant, mock_projector_client_validate: AsyncMock
) -> None:
    """Test aborting when attempting to configure the same projector twice."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={CONF_HOST: "1.2.3.4", CONF_TITLE: "Existing"},
    )
    entry.add_to_hass(hass)

    result = await _start_user_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert mock_projector_client_validate.await_count == 1
