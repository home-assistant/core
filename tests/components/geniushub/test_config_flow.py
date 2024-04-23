"""Test the Geniushub config flow."""
from http import HTTPStatus
import socket
import sys
from unittest.mock import patch

from aiohttp import ClientConnectionError as cce, ClientResponseError as cre

from homeassistant.components.geniushub import const
from homeassistant.components.geniushub.config_flow import (
    step_user_data_schema_v1,
    step_user_data_schema_v3,
)
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


async def test_step_user_data_schema_v1(hass: HomeAssistant) -> None:
    """Test step_user_data_schema."""
    result = step_user_data_schema_v1()
    assert str(result.schema["host"]) == "<class 'str'>"
    assert str(result.schema["username"]) == "<class 'str'>"
    assert str(result.schema["password"]) == "<class 'str'>"


async def test_step_user_data_schema_v3(hass: HomeAssistant) -> None:
    """Test step_user_data_schema."""
    result = step_user_data_schema_v3()
    assert str(result.schema["token"]) == "<class 'str'>"
    assert str(result.schema["mac"]) == "<class 'str'>"


async def test_form(hass: HomeAssistant) -> None:
    """Test manually setting up."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]


async def test_form_s_v1(hass: HomeAssistant) -> None:
    """Test manually setting up."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": SOURCE_USER}, data={"option_1_or_2": True}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_v1"
    assert not result["errors"]


async def test_form_s_v3(hass: HomeAssistant) -> None:
    """Test manually setting up."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": SOURCE_USER}, data={"option_1_or_2": False}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user_v3"
    assert not result["errors"]


async def test_form_v1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1."""
    entry = MockConfigEntry(
        domain=const.DOMAIN, unique_id="aabbccddeeff", data={"option_1_or_2": True}
    )
    entry.add_to_hass(hass)

    mock_dev_id = "aabbccddee"
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(const.DOMAIN, mock_dev_id)}
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "user_v1"}, data={"option_1_or_2": True}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_v3(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3."""
    entry = MockConfigEntry(
        domain=const.DOMAIN, unique_id="aabbccddeeff", data={"option_1_or_2": False}
    )
    entry.add_to_hass(hass)

    mock_dev_id = "aabbccddee"
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(const.DOMAIN, mock_dev_id)}
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "user_v3"}, data={"option_1_or_2": False}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_v1_good_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 with good data."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": True,
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
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v1"},
            data={
                "option_1_or_2": True,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "errors" not in result
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v1_ClientResponseError(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 ClientResponseError."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": True,
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
        side_effect=cre(request_info={}, history={}),
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v1"},
            data={
                "option_1_or_2": True,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v1_UNAUTHORIZED(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 UNAUTHORIZED."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": True,
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
        side_effect=cre(request_info={}, history={}, status=HTTPStatus.UNAUTHORIZED),
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v1"},
            data={
                "option_1_or_2": True,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unauthorized"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v1_timeout(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 with good data."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": True,
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
        side_effect=TimeoutError,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v1"},
            data={
                "option_1_or_2": True,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v1_invalid_host(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 with good data."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": True,
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
        side_effect=socket.gaierror,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v1"},
            data={
                "option_1_or_2": True,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v1_Exception(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 with good data."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": True,
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
        side_effect=Exception,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v1"},
            data={
                "option_1_or_2": True,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v3_good_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3 with good data."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": False,
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
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v3"},
            data={
                "option_1_or_2": False,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "errors" not in result
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v3_ClientResponseError(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3 ClientResponseError."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": False,
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
        side_effect=cre(request_info={}, history={}),
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v3"},
            data={
                "option_1_or_2": False,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v3_UNAUTHORIZED(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3 UNAUTHORIZED."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": False,
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
        side_effect=cre(request_info={}, history={}, status=HTTPStatus.UNAUTHORIZED),
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v3"},
            data={
                "option_1_or_2": False,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unauthorized_token"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v3_timeout(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3 timeout."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": False,
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
        side_effect=TimeoutError,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v3"},
            data={
                "option_1_or_2": False,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v3_invalid_host(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3 with good data."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": False,
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
        side_effect=socket.gaierror,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v3"},
            data={
                "option_1_or_2": False,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v3_Exception(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 with good data."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": False,
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
        side_effect=Exception,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v3"},
            data={
                "option_1_or_2": False,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v1_ClientConnectionError(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V1 with ClientConnectionError."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": True,
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
        side_effect=cce,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v1"},
            data={
                "option_1_or_2": True,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_v3_ClientConnectionError(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test form V3 with ClientConnectionError."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={
            "option_1_or_2": False,
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
        side_effect=cce,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": "user_v3"},
            data={
                "option_1_or_2": False,
                CONF_HOST: GENIUS_HOST,
                CONF_PASSWORD: GENIUS_PASSWORD,
                CONF_USERNAME: GENIUS_USERNAME,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
    assert len(mock_validate_input.mock_calls) == 1
