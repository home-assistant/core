"""Test Zeroconf multiple instance protection."""
from unittest.mock import Mock, patch

import zeroconf

from spencerassistant.components.zeroconf import async_get_instance
from spencerassistant.components.zeroconf.usage import install_multiple_zeroconf_catcher
from spencerassistant.setup import async_setup_component

DOMAIN = "zeroconf"


async def test_multiple_zeroconf_instances(
    hass, mock_async_zeroconf, mock_zeroconf, caplog
):
    """Test creating multiple zeroconf throws without an integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    zeroconf_instance = await async_get_instance(hass)

    install_multiple_zeroconf_catcher(zeroconf_instance)

    new_zeroconf_instance = zeroconf.Zeroconf()
    assert new_zeroconf_instance == zeroconf_instance

    assert "Zeroconf" in caplog.text


async def test_multiple_zeroconf_instances_gives_shared(
    hass, mock_async_zeroconf, mock_zeroconf, caplog
):
    """Test creating multiple zeroconf gives the shared instance to an integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    zeroconf_instance = await async_get_instance(hass)

    install_multiple_zeroconf_catcher(zeroconf_instance)

    correct_frame = Mock(
        filename="/config/custom_components/burncpu/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with patch(
        "spencerassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/spencer/dev/spencerassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            correct_frame,
            Mock(
                filename="/spencer/dev/spencerassistant/components/zeroconf/usage.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/spencer/dev/mdns/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        assert zeroconf.Zeroconf() == zeroconf_instance

    assert "custom_components/burncpu/light.py" in caplog.text
    assert "23" in caplog.text
    assert "self.light.is_on" in caplog.text
