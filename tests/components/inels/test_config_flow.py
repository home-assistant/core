"""Test config flow."""

from unittest.mock import MagicMock, patch

from inelsmqtt import InelsMqtt
from inelsmqtt.const import MQTT_TRANSPORT
import pytest

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import HA_INELS_PATH
from .common import DOMAIN, MockConfigEntry, config_flow, inels


@pytest.fixture
def default_config():
    """Return default MQTT configuration for testing."""
    return {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1883,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "pwd",
        MQTT_TRANSPORT: "tcp",
    }


@pytest.fixture(autouse=True)
def mock_is_available():
    """Mock test_connection inside InelsMqtt."""
    with patch(
        "inelsmqtt.InelsMqtt.test_connection", return_value=None
    ) as mock_available:
        yield mock_available


@pytest.fixture
def mock_try_connection():
    """Mock the try connection method."""
    with patch(f"{HA_INELS_PATH}.config_flow.try_connection") as mock_try:
        yield mock_try


@pytest.fixture
def mock_mqtt_client_test_connection():
    """Mock mqtt client."""

    def test_connection(self) -> None:
        """Mock test_connection the method."""
        return 6  # leads to unknown error

    with patch.object(InelsMqtt, "test_connection", test_connection) as mock_try:
        yield mock_try


async def test_user_config_flow_finished_successfully(
    hass: HomeAssistant, mock_try_connection, default_config
) -> None:
    """Test if we can finish config flow."""
    mock_try_connection.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result[CONF_TYPE] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        default_config,
    )

    assert result[CONF_TYPE] == "create_entry"
    assert result["result"].data == default_config

    assert len(mock_try_connection.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_code", "expected_error"),
    [
        (1, "mqtt_version"),
        (2, "forbidden_id"),
        (3, "cannot_connect"),
        (4, "invalid_auth"),
        (5, "unauthorized"),
        (6, "unknown"),
    ],
)
async def test_user_config_flow_errors(
    hass: HomeAssistant, mock_try_connection, error_code, expected_error, default_config
) -> None:
    """Test the config flow."""
    mock_try_connection.return_value = error_code

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result[CONF_TYPE] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        default_config,
    )

    assert result[CONF_TYPE] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    assert len(mock_try_connection.mock_calls) == 1


async def test_config_setup(
    hass: HomeAssistant, mock_try_connection, mock_is_available, default_config
) -> None:
    """Test configuration."""
    mock_try_connection.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result[CONF_TYPE] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        default_config,
    )

    assert result[CONF_TYPE] == "create_entry"
    assert result["result"].data == default_config

    mock_try_connection.assert_called_once_with(
        hass, "127.0.0.1", 1883, "test", "pwd", "tcp"
    )

    assert len(mock_is_available.mock_calls) == 1


async def test_async_unload_entry(hass: HomeAssistant, default_config) -> None:
    """Test the MQTT client associated with the entry is properly cleaned up."""

    mock_mqtt = MagicMock()
    inels_data = inels.InelsData(mqtt=mock_mqtt, devices=[])

    config_entry = MockConfigEntry(domain=DOMAIN, data=default_config)
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = inels_data

    with patch(
        f"{HA_INELS_PATH}.async_unload_entry", wraps=inels.async_unload_entry
    ) as mock_unload:
        unload_ok = await inels.async_unload_entry(hass, config_entry)

        assert unload_ok
        mock_unload.assert_called_once_with(hass, config_entry)

    mock_mqtt.unsubscribe_listeners.assert_called_once()
    mock_mqtt.disconnect.assert_called_once()


async def test_try_connection(mock_mqtt_client_test_connection, default_config) -> None:
    """Test the try_connection function."""

    assert (
        config_flow.try_connection(None, **default_config) == 6
    )  # checks that the correct value is propagated
