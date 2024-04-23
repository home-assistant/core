"""Test Zeroconf multiple instance protection."""

from unittest.mock import Mock, patch

import pytest
import zeroconf

from homeassistant.components.zeroconf import async_get_instance
from homeassistant.components.zeroconf.usage import install_multiple_zeroconf_catcher
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import extract_stack_to_frame

DOMAIN = "zeroconf"


async def test_multiple_zeroconf_instances(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
    mock_zeroconf: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test creating multiple zeroconf throws without an integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    zeroconf_instance = await async_get_instance(hass)

    install_multiple_zeroconf_catcher(zeroconf_instance)

    new_zeroconf_instance = zeroconf.Zeroconf()
    assert new_zeroconf_instance == zeroconf_instance

    assert "Zeroconf" in caplog.text


async def test_multiple_zeroconf_instances_gives_shared(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
    mock_zeroconf: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test creating multiple zeroconf gives the shared instance to an integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    zeroconf_instance = await async_get_instance(hass)

    install_multiple_zeroconf_catcher(zeroconf_instance)

    correct_frame = Mock(
        filename="/config/custom_components/burncpu/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value=correct_frame.line,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/dev/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    correct_frame,
                    Mock(
                        filename="/home/dev/homeassistant/components/zeroconf/usage.py",
                        lineno="23",
                        line="self.light.is_on",
                    ),
                    Mock(
                        filename="/home/dev/mdns/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        assert zeroconf.Zeroconf() == zeroconf_instance

    assert "custom_components/burncpu/light.py" in caplog.text
    assert "23" in caplog.text
    assert "self.light.is_on" in caplog.text
