"""The tests for the Logger component."""
from collections import defaultdict

from homeassistant.components import logger
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch


async def test_setting_level(hass):
    """Test we set log levels."""
    mocks = defaultdict(Mock)

    with patch("logging.getLogger", mocks.__getitem__):
        assert await async_setup_component(
            hass,
            "logger",
            {
                "logger": {
                    "default": "warning",
                    "logs": {
                        "test": "info",
                        "test.child": "debug",
                        "test.child.child": "warning",
                    },
                }
            },
        )

    assert len(mocks) == 4

    assert len(mocks[""].setLevel.mock_calls) == 1
    assert mocks[""].setLevel.mock_calls[0][1][0] == logger.LOGSEVERITY["WARNING"]

    assert len(mocks["test"].setLevel.mock_calls) == 1
    assert mocks["test"].setLevel.mock_calls[0][1][0] == logger.LOGSEVERITY["INFO"]

    assert len(mocks["test.child"].setLevel.mock_calls) == 1
    assert (
        mocks["test.child"].setLevel.mock_calls[0][1][0] == logger.LOGSEVERITY["DEBUG"]
    )

    assert len(mocks["test.child.child"].setLevel.mock_calls) == 1
    assert (
        mocks["test.child.child"].setLevel.mock_calls[0][1][0]
        == logger.LOGSEVERITY["WARNING"]
    )

    # Test set default level
    with patch("logging.getLogger", mocks.__getitem__):
        await hass.services.async_call(
            "logger", "set_default_level", {"level": "fatal"}, blocking=True
        )
    assert len(mocks[""].setLevel.mock_calls) == 2
    assert mocks[""].setLevel.mock_calls[1][1][0] == logger.LOGSEVERITY["FATAL"]

    # Test update other loggers
    with patch("logging.getLogger", mocks.__getitem__):
        await hass.services.async_call(
            "logger",
            "set_level",
            {"test.child": "info", "new_logger": "notset"},
            blocking=True,
        )
    assert len(mocks) == 5

    assert len(mocks["test.child"].setLevel.mock_calls) == 2
    assert (
        mocks["test.child"].setLevel.mock_calls[1][1][0] == logger.LOGSEVERITY["INFO"]
    )

    assert len(mocks["new_logger"].setLevel.mock_calls) == 1
    assert (
        mocks["new_logger"].setLevel.mock_calls[0][1][0] == logger.LOGSEVERITY["NOTSET"]
    )
