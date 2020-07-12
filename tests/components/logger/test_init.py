"""The tests for the Logger component."""
from collections import defaultdict
import logging

from homeassistant.components import logger
from homeassistant.helpers.logging import LOGSEVERITY
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch

HASS_NS = "homeassistant"
COMPONENTS_NS = f"{HASS_NS}.components"
ZONE_NS = f"{COMPONENTS_NS}.zone"
GROUP_NS = f"{COMPONENTS_NS}.group"
CONFIGED_NS = "otherlibx"
UNCONFIG_NS = "unconfigurednamespace"


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
        await hass.async_block_till_done()

    assert len(mocks) == 4

    assert len(mocks[""].setLevel.mock_calls) == 1
    assert mocks[""].setLevel.mock_calls[0][1][0] == LOGSEVERITY["WARNING"]

    assert len(mocks["test"].setLevel.mock_calls) == 1
    assert mocks["test"].setLevel.mock_calls[0][1][0] == LOGSEVERITY["INFO"]

    assert len(mocks["test.child"].setLevel.mock_calls) == 1
    assert mocks["test.child"].setLevel.mock_calls[0][1][0] == LOGSEVERITY["DEBUG"]

    assert len(mocks["test.child.child"].setLevel.mock_calls) == 1
    assert (
        mocks["test.child.child"].setLevel.mock_calls[0][1][0] == LOGSEVERITY["WARNING"]
    )

    # Test set default level
    with patch("logging.getLogger", mocks.__getitem__):
        await hass.services.async_call(
            "logger", "set_default_level", {"level": "fatal"}, blocking=True
        )
    assert len(mocks[""].setLevel.mock_calls) == 2
    assert mocks[""].setLevel.mock_calls[1][1][0] == LOGSEVERITY["FATAL"]

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
    assert mocks["test.child"].setLevel.mock_calls[1][1][0] == LOGSEVERITY["INFO"]

    assert len(mocks["new_logger"].setLevel.mock_calls) == 1
    assert mocks["new_logger"].setLevel.mock_calls[0][1][0] == LOGSEVERITY["NOTSET"]


async def test_loading_integration_after_can_set_level(hass):
    """Test logger propagation."""
    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        "logger",
        {
            "logger": {
                "default": "critical",
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
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "zone", {})
    await hass.async_block_till_done()

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger("").isEnabledFor(logging.CRITICAL) is True

    logging.getLogger(UNCONFIG_NS).level == logging.NOTSET
    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.DEBUG) is False
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.DEBUG) is False
    )

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
        logger.DOMAIN, "set_level", {f"{UNCONFIG_NS}.any": "debug"}
    )
    await hass.async_block_till_done()

    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.DEBUG) is False
    logging.getLogger(UNCONFIG_NS).level == logging.NOTSET
    assert logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.DEBUG) is True
    logging.getLogger(f"{UNCONFIG_NS}.any").level == logging.DEBUG
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.DEBUG) is True
    )
    logging.getLogger(UNCONFIG_NS).level == logging.NOTSET

    await hass.services.async_call(
        logger.DOMAIN, "set_default_level", {"level": "debug"}
    )
    await hass.async_block_till_done()

    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.DEBUG) is True
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.DEBUG) is True
    )
    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is True

    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.DEBUG) is False


async def test_loading_integration_after_can_set_level_with_default_debug(hass):
    """Test logger propagation."""
    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        "logger",
        {
            "logger": {
                "default": "debug",
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
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "zone", {})
    await hass.async_block_till_done()

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger("").isEnabledFor(logging.CRITICAL) is True

    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.DEBUG) is True
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.DEBUG) is True
    )

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
