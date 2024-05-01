"""Test the Geniushub config flow."""

from http import HTTPStatus
import socket
import sys
from unittest.mock import patch

from aiohttp import ClientConnectionError as cce, ClientResponseError as cre

from homeassistant import config_entries
from homeassistant.components.geniushub import const
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

GENIUS_USERNAME = "username"
GENIUS_PASSWORD = "password"
GENIUS_HOST = "192.168.1.1"

sys.exc_info()


async def test_form_menu(hass: HomeAssistant) -> None:
    """Test manually setting up menu."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_form_v1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1."""
    entry = MockConfigEntry(domain=const.DOMAIN, unique_id="aabbccddeeff")
    entry.add_to_hass(hass)

    mock_dev_id = "aabbccddee"
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(const.DOMAIN, mock_dev_id)}
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "v1_api"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_api"


async def test_form_v3(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3."""
    entry = MockConfigEntry(domain=const.DOMAIN, unique_id="aabbccddeeff")
    entry.add_to_hass(hass)

    mock_dev_id = "aabbccddee"
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(const.DOMAIN, mock_dev_id)}
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "v3_api"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3_api"


async def test_form_v3_device_added_twice(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3 with good data device added twice."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            CONF_HOST: GENIUS_HOST,
            CONF_PASSWORD: GENIUS_PASSWORD,
            CONF_USERNAME: GENIUS_USERNAME,
        },
    )
    entry.add_to_hass(hass)

    mock_dev_id = "aabbccddee"
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(const.DOMAIN, mock_dev_id)}
    )

    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        return_value={"title": "Title"},
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.ABORT


async def test_form_v1_good_data(hass: HomeAssistant) -> None:
    """Test form V1 with good data."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        return_value={"title": "Title"},
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v1_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "errors" not in result


async def test_form_v1_ClientResponseError(hass: HomeAssistant) -> None:
    """Test form V1 ClientResponseError."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cre(request_info={}, history={}),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v1_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"


async def test_form_v1_UNAUTHORIZED(hass: HomeAssistant) -> None:
    """Test form V1 UNAUTHORIZED."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cre(request_info={}, history={}, status=HTTPStatus.UNAUTHORIZED),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v1_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unauthorized_token"


async def test_form_v1_timeout(hass: HomeAssistant) -> None:
    """Test form V1 with timeout."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v1_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_form_v1_invalid_host(hass: HomeAssistant) -> None:
    """Test form V1 with invalid host."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=socket.gaierror,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v1_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"


async def test_form_v1_Exception(hass: HomeAssistant) -> None:
    """Test form V1 with exception."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v1_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_form_v3_good_data(hass: HomeAssistant) -> None:
    """Test form V3 with good data."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        return_value={"title": "Title"},
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "errors" not in result


async def test_form_v3_ClientResponseError(hass: HomeAssistant) -> None:
    """Test form V3 ClientResponseError."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cre(request_info={}, history={}),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"


async def test_form_v3_UNAUTHORIZED(hass: HomeAssistant) -> None:
    """Test form V3 UNAUTHORIZED."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cre(request_info={}, history={}, status=HTTPStatus.UNAUTHORIZED),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unauthorized"


async def test_form_v3_timeout(hass: HomeAssistant) -> None:
    """Test form V3 timeout."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_form_v3_invalid_host(hass: HomeAssistant) -> None:
    """Test form V3 with invalid host."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=socket.gaierror,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"


async def test_form_v3_Exception(hass: HomeAssistant) -> None:
    """Test form V3 with exception."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_form_v1_ClientConnectionError(hass: HomeAssistant) -> None:
    """Test form V1 with ClientConnectionError."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cce,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v1_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_form_v3_ClientConnectionError(hass: HomeAssistant) -> None:
    """Test form V3 with ClientConnectionError."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cce,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "v3_api"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_form_import_good_data(hass: HomeAssistant) -> None:
    """Test import form with good data."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        return_value={"title": "Title"},
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "errors" not in result


async def test_form_import_ClientResponseError(hass: HomeAssistant) -> None:
    """Test import form ClientResponseError."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cre(request_info={}, history={}),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "import"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"


async def test_form_import_UNAUTHORIZED(hass: HomeAssistant) -> None:
    """Test import form UNAUTHORIZED."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cre(request_info={}, history={}, status=HTTPStatus.UNAUTHORIZED),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "import"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unauthorized"


async def test_form_import_timeout(hass: HomeAssistant) -> None:
    """Test import form timeout."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "import"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_form_import_invalid_host(hass: HomeAssistant) -> None:
    """Test import form with invalid host."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=socket.gaierror,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "import"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"


async def test_form_import_Exception(hass: HomeAssistant) -> None:
    """Test import form with exception."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "import"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_form_import_ClientConnectionError(hass: HomeAssistant) -> None:
    """Test import form with ClientConnectionError."""
    with patch(
        "homeassistant.components.geniushub.config_flow.validate_input",
        side_effect=cce,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "import"},
            data={
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
