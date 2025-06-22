"""The tests for the Logger component."""

from collections import defaultdict
import datetime
import logging
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import logger
from homeassistant.components.logger import LOGSEVERITY
from homeassistant.components.logger.helpers import SAVE_DELAY_LONG
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_call_logger_set_level, async_fire_time_changed

HASS_NS = "unused.homeassistant"
COMPONENTS_NS = f"{HASS_NS}.components"
ZONE_NS = f"{COMPONENTS_NS}.zone"
GROUP_NS = f"{COMPONENTS_NS}.group"
CONFIGED_NS = "otherlibx"
UNCONFIG_NS = "unconfigurednamespace"
INTEGRATION = "test_component"
INTEGRATION_NS = f"homeassistant.components.{INTEGRATION}"


async def test_log_filtering(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test logging filters."""

    assert await async_setup_component(
        hass,
        "logger",
        {
            "logger": {
                "default": "warning",
                "logs": {
                    "test.filter": "info",
                },
                "filters": {
                    "test.filter": [
                        "doesntmatchanything",
                        ".*shouldfilterall.*",
                        "^filterthis:.*",
                        "in the middle",
                    ],
                    "test.other_filter": [".*otherfilterer"],
                },
            }
        },
    )
    await hass.async_block_till_done()

    filter_logger = logging.getLogger("test.filter")

    def msg_test(logger, result, message, *args):
        logger.error(message, *args)
        formatted_message = message % args
        assert (formatted_message in caplog.text) == result
        caplog.clear()

    msg_test(
        filter_logger, False, "this line containing shouldfilterall should be filtered"
    )
    msg_test(filter_logger, True, "this line should not be filtered filterthis:")
    msg_test(filter_logger, False, "this in the middle should be filtered")
    msg_test(filter_logger, False, "filterthis: should be filtered")
    msg_test(filter_logger, False, "format string shouldfilter%s", "all")
    msg_test(filter_logger, True, "format string shouldfilter%s", "not")

    # Filtering should work even if log level is modified
    async with async_call_logger_set_level(
        "test.filter", "WARNING", hass=hass, caplog=caplog
    ):
        assert filter_logger.getEffectiveLevel() == logging.WARNING
        msg_test(
            filter_logger,
            False,
            "this line containing shouldfilterall should still be filtered",
        )

        # Filtering should be scoped to a service
        msg_test(
            filter_logger,
            True,
            "this line containing otherfilterer should not be filtered",
        )
        msg_test(
            logging.getLogger("test.other_filter"),
            False,
            "this line containing otherfilterer SHOULD be filtered",
        )


async def test_setting_level(hass: HomeAssistant) -> None:
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
        await hass.async_block_till_done()

    assert len(mocks) == 4

    assert len(mocks[""].orig_setLevel.mock_calls) == 1
    assert mocks[""].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["WARNING"]

    assert len(mocks["test"].orig_setLevel.mock_calls) == 1
    assert mocks["test"].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["INFO"]

    assert len(mocks["test.child"].orig_setLevel.mock_calls) == 1
    assert mocks["test.child"].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["DEBUG"]

    assert len(mocks["test.child.child"].orig_setLevel.mock_calls) == 1
    assert (
        mocks["test.child.child"].orig_setLevel.mock_calls[0][1][0]
        == LOGSEVERITY["WARNING"]
    )

    # Test set default level
    with patch("logging.getLogger", mocks.__getitem__):
        await hass.services.async_call(
            "logger", "set_default_level", {"level": "fatal"}, blocking=True
        )
    assert len(mocks[""].orig_setLevel.mock_calls) == 2
    assert mocks[""].orig_setLevel.mock_calls[1][1][0] == LOGSEVERITY["FATAL"]

    # Test update other loggers
    with patch("logging.getLogger", mocks.__getitem__):
        await hass.services.async_call(
            "logger",
            "set_level",
            {"test.child": "info", "new_logger": "notset"},
            blocking=True,
        )
    assert len(mocks) == 5

    assert len(mocks["test.child"].orig_setLevel.mock_calls) == 2
    assert mocks["test.child"].orig_setLevel.mock_calls[1][1][0] == LOGSEVERITY["INFO"]

    assert len(mocks["new_logger"].orig_setLevel.mock_calls) == 1
    assert (
        mocks["new_logger"].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["NOTSET"]
    )


async def test_can_set_level_from_yaml(hass: HomeAssistant) -> None:
    """Test logger propagation."""

    assert await async_setup_component(
        hass,
        "logger",
        {
            "logger": {
                "logs": {
                    CONFIGED_NS: "warning",
                    f"{CONFIGED_NS}.info": "info",
                    f"{CONFIGED_NS}.debug": "debug",
                    HASS_NS: "warning",
                    COMPONENTS_NS: "info",
                    ZONE_NS: "debug",
                    GROUP_NS: "info",
                },
            }
        },
    )
    await _assert_log_levels(hass)
    _reset_logging()


async def test_can_set_level_from_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test setting up logs from store."""
    hass_storage["core.logger"] = {
        "data": {
            "logs": {
                CONFIGED_NS: {
                    "level": "WARNING",
                    "persistence": "once",
                    "type": "module",
                },
                f"{CONFIGED_NS}.info": {
                    "level": "INFO",
                    "persistence": "once",
                    "type": "module",
                },
                f"{CONFIGED_NS}.debug": {
                    "level": "DEBUG",
                    "persistence": "once",
                    "type": "module",
                },
                HASS_NS: {"level": "WARNING", "persistence": "once", "type": "module"},
                COMPONENTS_NS: {
                    "level": "INFO",
                    "persistence": "once",
                    "type": "module",
                },
                ZONE_NS: {"level": "DEBUG", "persistence": "once", "type": "module"},
                GROUP_NS: {"level": "INFO", "persistence": "once", "type": "module"},
            }
        },
        "key": "core.logger",
        "version": 1,
    }
    assert await async_setup_component(hass, "logger", {})
    await _assert_log_levels(hass)
    _reset_logging()


async def _assert_log_levels(hass: HomeAssistant) -> None:
    assert logging.getLogger(UNCONFIG_NS).level == logging.NOTSET
    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.CRITICAL) is True
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.CRITICAL) is True
    )
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.CRITICAL)
        is True
    )

    assert logging.getLogger(CONFIGED_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(CONFIGED_NS).isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(f"{CONFIGED_NS}.any").isEnabledFor(logging.WARNING) is True
    assert (
        logging.getLogger(f"{CONFIGED_NS}.any.any").isEnabledFor(logging.WARNING)
        is True
    )
    assert logging.getLogger(f"{CONFIGED_NS}.info").isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(f"{CONFIGED_NS}.info").isEnabledFor(logging.INFO) is True
    assert (
        logging.getLogger(f"{CONFIGED_NS}.info.any").isEnabledFor(logging.DEBUG)
        is False
    )
    assert (
        logging.getLogger(f"{CONFIGED_NS}.info.any").isEnabledFor(logging.INFO) is True
    )
    assert logging.getLogger(f"{CONFIGED_NS}.debug").isEnabledFor(logging.DEBUG) is True
    assert (
        logging.getLogger(f"{CONFIGED_NS}.debug.any").isEnabledFor(logging.DEBUG)
        is True
    )

    assert logging.getLogger(HASS_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(HASS_NS).isEnabledFor(logging.WARNING) is True

    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.INFO) is True

    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.INFO) is True

    assert logging.getLogger(f"{GROUP_NS}.any").isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(f"{GROUP_NS}.any").isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(f"{GROUP_NS}.any").isEnabledFor(logging.INFO) is True

    assert logging.getLogger(ZONE_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(f"{ZONE_NS}.any").isEnabledFor(logging.DEBUG) is True

    await hass.services.async_call(
        logger.DOMAIN, "set_level", {f"{UNCONFIG_NS}.any": "debug"}, blocking=True
    )

    assert logging.getLogger(UNCONFIG_NS).level == logging.NOTSET
    assert logging.getLogger(f"{UNCONFIG_NS}.any").level == logging.DEBUG
    assert logging.getLogger(UNCONFIG_NS).level == logging.NOTSET

    await hass.services.async_call(
        logger.DOMAIN, "set_default_level", {"level": "debug"}, blocking=True
    )

    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.DEBUG) is True
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.DEBUG) is True
    )
    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is True

    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.DEBUG) is False

    logging.getLogger(CONFIGED_NS).setLevel(logging.INFO)
    assert logging.getLogger(CONFIGED_NS).level == logging.WARNING

    logging.getLogger("").setLevel(logging.NOTSET)


def _reset_logging():
    """Reset loggers."""
    logging.getLogger(CONFIGED_NS).orig_setLevel(logging.NOTSET)
    logging.getLogger(f"{CONFIGED_NS}.info").orig_setLevel(logging.NOTSET)
    logging.getLogger(f"{CONFIGED_NS}.debug").orig_setLevel(logging.NOTSET)
    logging.getLogger(HASS_NS).orig_setLevel(logging.NOTSET)
    logging.getLogger(COMPONENTS_NS).orig_setLevel(logging.NOTSET)
    logging.getLogger(ZONE_NS).orig_setLevel(logging.NOTSET)
    logging.getLogger(GROUP_NS).orig_setLevel(logging.NOTSET)
    logging.getLogger(INTEGRATION_NS).orig_setLevel(logging.NOTSET)


async def test_can_set_integration_level_from_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test setting up integration logs from store."""
    hass_storage["core.logger"] = {
        "data": {
            "logs": {
                INTEGRATION: {
                    "level": "WARNING",
                    "persistence": "once",
                    "type": "integration",
                },
            }
        },
        "key": "core.logger",
        "version": 1,
    }
    assert await async_setup_component(hass, "logger", {})

    assert logging.getLogger(INTEGRATION_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(INTEGRATION_NS).isEnabledFor(logging.WARNING) is True

    _reset_logging()


async def test_chattier_log_level_wins_1(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test chattier log level in store takes precedence."""
    hass_storage["core.logger"] = {
        "data": {
            "logs": {
                INTEGRATION_NS: {
                    "level": "DEBUG",
                    "persistence": "once",
                    "type": "module",
                },
            }
        },
        "key": "core.logger",
        "version": 1,
    }
    assert await async_setup_component(
        hass,
        "logger",
        {
            "logger": {
                "logs": {
                    INTEGRATION_NS: "warning",
                }
            }
        },
    )

    assert logging.getLogger(INTEGRATION_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(INTEGRATION_NS).isEnabledFor(logging.WARNING) is True

    _reset_logging()


async def test_chattier_log_level_wins_2(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test chattier log level in yaml takes precedence."""
    hass_storage["core.logger"] = {
        "data": {
            "logs": {
                INTEGRATION_NS: {
                    "level": "WARNING",
                    "persistence": "once",
                    "type": "module",
                },
            }
        },
        "key": "core.logger",
        "version": 1,
    }
    assert await async_setup_component(
        hass, "logger", {"logger": {"logs": {INTEGRATION_NS: "debug"}}}
    )

    assert logging.getLogger(INTEGRATION_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(INTEGRATION_NS).isEnabledFor(logging.WARNING) is True

    _reset_logging()


async def test_log_once_removed_from_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test logs with persistence "once" are removed from the store at startup."""
    store_contents = {
        "data": {
            "logs": {
                ZONE_NS: {"type": "module", "level": "DEBUG", "persistence": "once"}
            }
        },
        "key": "core.logger",
        "version": 1,
    }
    hass_storage["core.logger"] = store_contents

    assert await async_setup_component(hass, "logger", {})

    assert hass_storage["core.logger"]["data"] == store_contents["data"]

    async_fire_time_changed(
        hass, dt_util.utcnow() + datetime.timedelta(seconds=SAVE_DELAY_LONG)
    )
    await hass.async_block_till_done()

    assert hass_storage["core.logger"]["data"] == {"logs": {}}
