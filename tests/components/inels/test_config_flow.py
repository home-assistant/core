"""Test config flow."""

from unittest.mock import MagicMock, patch

from inelsmqtt import InelsMqtt
from inelsmqtt.const import MQTT_TRANSPORT
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import HA_INELS_PATH
from .common import MockConfigEntry, config_flow, inels


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


@pytest.fixture
def altered_config():
    """Fixture for an altered MQTT configuration."""
    return {
        CONF_HOST: "192.168.1.2",
        CONF_PORT: 1884,
        CONF_USERNAME: "new_user",
        CONF_PASSWORD: "new_pwd",
        MQTT_TRANSPORT: "websockets",
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


async def test_config_setup(
    hass: HomeAssistant, mock_try_connection, mock_is_available, default_config
) -> None:
    """Test configuration."""
    mock_try_connection.return_value = None

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result[CONF_TYPE] == data_entry_flow.RESULT_TYPE_FORM

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


async def test_async_unload_entry_removes_domain(hass: HomeAssistant) -> None:
    """Test that unloading the last config entry removes the DOMAIN from hass.data."""
    mock_client = MagicMock()

    hass.data.setdefault(inels.DOMAIN, {})
    hass.data[inels.DOMAIN]["entry_id"] = {inels.const.BROKER: mock_client}

    config_entry = MockConfigEntry(domain=inels.DOMAIN, entry_id="entry_id")
    config_entry.add_to_hass(hass)

    with patch(
        f"{HA_INELS_PATH}.async_unload_entry", wraps=inels.async_unload_entry
    ) as mock_unload:
        unload_ok = await inels.async_unload_entry(hass, config_entry)

        assert unload_ok
        assert inels.DOMAIN not in hass.data
        mock_unload.assert_called_once_with(hass, config_entry)


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test only on single instance of inels integration."""
    MockConfigEntry(domain=inels.DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result[CONF_TYPE] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_try_connection(mock_mqtt_client_test_connection, default_config) -> None:
    """Test the try_connection function."""

    assert (
        config_flow.try_connection(None, **default_config) == 6
    )  # checks that the correct value is propagated


async def test_test_connect_to_error() -> None:
    """Test the test_connect function."""
    assert config_flow.connect_val_to_error(1) == "mqtt_version"

    assert config_flow.connect_val_to_error(None) == "unknown"
