"""Define fixtures available for all tests."""

import pytest

from homeassistant.components.switchbot.const import (
    CONF_CURTAIN_SPEED,
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    CONF_RETRY_COUNT,
    CONF_ROLLER_SHADE_QUIET_MODE,
    DEFAULT_CURTAIN_SPEED,
    DEFAULT_RETRY_COUNT,
    DEFAULT_ROLLER_SHADE_QUIET_MODE,
    DOMAIN,
    SupportedModels,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SENSOR_TYPE

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_entry_factory():
    """Fixture to create a MockConfigEntry with a customizable sensor type."""

    def _create_entry(sensor_type: str = "curtain") -> MockConfigEntry:
        options: dict[str, int | bool] = {CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT}
        if sensor_type == SupportedModels.CURTAIN:
            options[CONF_CURTAIN_SPEED] = DEFAULT_CURTAIN_SPEED
        if sensor_type == SupportedModels.ROLLER_SHADE:
            options[CONF_ROLLER_SHADE_QUIET_MODE] = DEFAULT_ROLLER_SHADE_QUIET_MODE
        return MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
                CONF_NAME: "test-name",
                CONF_SENSOR_TYPE: sensor_type,
            },
            unique_id="aabbccddeeff",
            version=1,
            minor_version=3,
            options=options,
        )

    return _create_entry


@pytest.fixture
def mock_entry_encrypted_factory():
    """Fixture to create a MockConfigEntry with an encryption key and a customizable sensor type."""

    def _create_entry(sensor_type: str = "lock") -> MockConfigEntry:
        options: dict[str, int | bool] = {CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT}
        if sensor_type == SupportedModels.CURTAIN:
            options[CONF_CURTAIN_SPEED] = DEFAULT_CURTAIN_SPEED
        if sensor_type == SupportedModels.ROLLER_SHADE:
            options[CONF_ROLLER_SHADE_QUIET_MODE] = DEFAULT_ROLLER_SHADE_QUIET_MODE
        return MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
                CONF_NAME: "test-name",
                CONF_SENSOR_TYPE: sensor_type,
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
            unique_id="aabbccddeeff",
            version=1,
            minor_version=3,
            options=options,
        )

    return _create_entry
