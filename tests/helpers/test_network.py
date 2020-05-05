"""Test network helper."""
import pytest

from homeassistant.components import cloud
import homeassistant.config as config_util
from homeassistant.core import HomeAssistant
from homeassistant.helpers import network
from homeassistant.helpers.network import NoURLAvailableError, async_get_url

from tests.async_mock import Mock, patch


@pytest.fixture(autouse=True)
def mock_local_ip():
    """Mock the call to get_local_ip to return a fake internal IP address."""
    with patch(
        "homeassistant.helpers.network.get_local_ip", return_value="192.168.123.123"
    ) as local_ip:
        yield local_ip


async def test_get_external_url(hass):
    """Test get_external_url."""
    assert network.async_get_external_url(hass) is None

    hass.config.api = Mock(base_url="http://192.168.1.100:8123")

    assert network.async_get_external_url(hass) is None

    hass.config.api = Mock(base_url="http://example.duckdns.org:8123")

    assert network.async_get_external_url(hass) == "http://example.duckdns.org:8123"

    hass.config.components.add("cloud")

    assert network.async_get_external_url(hass) == "http://example.duckdns.org:8123"

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        side_effect=cloud.CloudNotAvailable,
    ):
        assert network.async_get_external_url(hass) == "http://example.duckdns.org:8123"

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert network.async_get_external_url(hass) == "https://example.nabu.casa"


async def test_get_url_ip(hass: HomeAssistant):
    """Test getting an instance URL that only can result in an internal IP."""
    assert hass.config.external_url is None
    assert hass.config.internal_url is None

    hass.config.api = Mock(use_ssl=False, port=8123, base_url=None)

    assert async_get_url(hass) == "http://192.168.123.123:8123"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, allow_local=False)

    hass.config.api = Mock(use_ssl=False, port=80, base_url=None)

    assert async_get_url(hass) == "http://192.168.123.123"
    assert async_get_url(hass, require_standard_port=True) == "http://192.168.123.123"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, allow_local=False)


async def test_get_url_internal(hass: HomeAssistant):
    """Test getting an instance URL when the user has set an internal URL."""
    assert hass.config.internal_url is None
    assert hass.config.external_url is None

    # Test with internal URL: http://example.local:8123
    await config_util.async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    assert hass.config.internal_url == "http://example.local:8123"
    assert hass.config.external_url is None

    assert async_get_url(hass) == "http://example.local:8123"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, allow_local=False)

    # Test with internal URL: http://example.local:80/
    await config_util.async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:80/"},
    )

    assert hass.config.internal_url == "http://example.local:80/"
    assert async_get_url(hass) == "http://example.local"
    assert async_get_url(hass, require_standard_port=True) == "http://example.local"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, allow_local=False)

    # Test with internal url: http://example.local:8123
    await config_util.async_process_ha_core_config(
        hass, {"internal_url": "https://example.local/"},
    )
    assert hass.config.internal_url == "https://example.local/"
    assert async_get_url(hass) == "https://example.local"
    assert async_get_url(hass, require_ssl=True) == "https://example.local"
    assert async_get_url(hass, require_standard_port=True) == "https://example.local"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, allow_local=False)

    # Test with internal URL: https://example.local:80
    await config_util.async_process_ha_core_config(
        hass, {"internal_url": "https://example.local:80"},
    )
    assert hass.config.internal_url == "https://example.local:80"
    assert async_get_url(hass) == "https://example.local:80"
    assert async_get_url(hass, require_ssl=True) == "https://example.local:80"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, allow_local=False)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, allow_local=False)


async def test_get_url_external(hass: HomeAssistant):
    """Test getting an instance URL when the user has set an external URL."""
    assert hass.config.internal_url is None
    assert hass.config.external_url is None

    # Test with external URL: http://www.example.com:8123
    await config_util.async_process_ha_core_config(
        hass, {"external_url": "http://www.example.com:8123"},
    )

    assert hass.config.internal_url is None
    assert hass.config.external_url == "http://www.example.com:8123"

    assert async_get_url(hass) == "http://www.example.com:8123"
    assert async_get_url(hass, allow_local=False) == "http://www.example.com:8123"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)

    # Test with external URL: http://www.example.com:80/
    await config_util.async_process_ha_core_config(
        hass, {"external_url": "http://www.example.com:80/"},
    )

    assert hass.config.external_url == "http://www.example.com:80/"
    assert async_get_url(hass) == "http://www.example.com"
    assert async_get_url(hass, require_standard_port=True) == "http://www.example.com"
    assert async_get_url(hass, allow_local=False) == "http://www.example.com"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)

    # Test with external url: https://www.example.com/
    await config_util.async_process_ha_core_config(
        hass, {"external_url": "https://www.example.com/"},
    )
    assert hass.config.external_url == "https://www.example.com/"
    assert async_get_url(hass) == "https://www.example.com"
    assert async_get_url(hass, require_ssl=True) == "https://www.example.com"
    assert async_get_url(hass, require_standard_port=True) == "https://www.example.com"
    assert async_get_url(hass, allow_local=False) == "https://www.example.com"

    # Test with external url: https://www.example.com:443
    await config_util.async_process_ha_core_config(
        hass, {"external_url": "https://www.example.com:443"},
    )
    assert hass.config.external_url == "https://www.example.com:443"
    assert async_get_url(hass) == "https://www.example.com"
    assert async_get_url(hass, require_ssl=True) == "https://www.example.com"
    assert async_get_url(hass, require_standard_port=True) == "https://www.example.com"
    assert async_get_url(hass, allow_local=False) == "https://www.example.com"

    # Test with external URL: https://www.example.com:80
    await config_util.async_process_ha_core_config(
        hass, {"external_url": "https://www.example.com:80"},
    )
    assert hass.config.external_url == "https://www.example.com:80"
    assert async_get_url(hass) == "https://www.example.com:80"
    assert async_get_url(hass, require_ssl=True) == "https://www.example.com:80"
    assert async_get_url(hass, allow_local=False) == "https://www.example.com:80"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_standard_port=True)

    # Test with external URL: https://192.168.0.1
    await config_util.async_process_ha_core_config(
        hass, {"external_url": "https://192.168.0.1"},
    )
    assert hass.config.external_url == "https://192.168.0.1"
    assert async_get_url(hass) == "https://192.168.0.1"
    assert async_get_url(hass, require_standard_port=True) == "https://192.168.0.1"
    assert async_get_url(hass, allow_local=False) == "https://192.168.0.1"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)


async def test_get_url_cloud(hass: HomeAssistant):
    """Test getting an instance URL when the user has set an external URL."""
    assert hass.config.internal_url is None
    assert hass.config.external_url is None

    hass.config.components.add("cloud")

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert async_get_url(hass, allow_local=False) == "https://example.nabu.casa"
        assert async_get_url(hass, require_ssl=True) == "https://example.nabu.casa"

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        side_effect=cloud.CloudNotAvailable,
    ):
        with pytest.raises(NoURLAvailableError):
            async_get_url(hass, allow_local=False)

        with pytest.raises(NoURLAvailableError):
            async_get_url(hass, require_ssl=True)


async def test_get_url_fallback(hass: HomeAssistant):
    """Test getting an instance URL using fallback scenarios."""
    assert hass.config.internal_url is None
    assert hass.config.external_url is None

    # Test fallback to IP URL with internal URL set
    hass.config.api = Mock(use_ssl=False, port=80, base_url=None)
    await config_util.async_process_ha_core_config(
        hass, {"internal_url": "https://example.local:8123"},
    )

    assert hass.config.internal_url == "https://example.local:8123"
    assert async_get_url(hass) == "https://example.local:8123"
    assert async_get_url(hass, require_standard_port=True) == "http://192.168.123.123"

    # Test not falling back to IP URL
    hass.config.api = Mock(use_ssl=True, port=443, base_url=None)
    await config_util.async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )
    assert async_get_url(hass) == "http://example.local:8123"
    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_ssl=True)

    hass.config.api = Mock(use_ssl=False, port=8123, base_url=None)
    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_standard_port=True)

    # Test falling back to external URL
    hass.config.api = Mock(use_ssl=True, port=443, base_url=None)
    await config_util.async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://example.local:8123",
            "external_url": "https://www.example.com:8123",
        },
    )
    assert hass.config.internal_url == "http://example.local:8123"
    assert hass.config.external_url == "https://www.example.com:8123"
    assert async_get_url(hass) == "http://example.local:8123"
    assert async_get_url(hass, require_ssl=True) == "https://www.example.com:8123"

    with pytest.raises(NoURLAvailableError):
        async_get_url(hass, require_standard_port=True)

    await config_util.async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://example.local:8123",
            "external_url": "https://www.example.com",
        },
    )
    assert hass.config.internal_url == "http://example.local:8123"
    assert hass.config.external_url == "https://www.example.com"
    assert async_get_url(hass) == "http://example.local:8123"
    assert async_get_url(hass, require_ssl=True) == "https://www.example.com"
    assert async_get_url(hass, require_standard_port=True) == "https://www.example.com"
    assert async_get_url(hass, allow_local=False) == "https://www.example.com"
    assert (
        async_get_url(
            hass, allow_local=False, require_ssl=True, require_standard_port=True
        )
        == "https://www.example.com"
    )

    # Test fallback to Cloud URL
    hass.config.components.add("cloud")
    await config_util.async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://example.local:8123",
            "external_url": "https://www.example.com:8123",
        },
    )
    assert hass.config.internal_url == "http://example.local:8123"
    assert hass.config.external_url == "https://www.example.com:8123"

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert async_get_url(hass, require_ssl=True) == "https://www.example.com:8123"
        assert (
            async_get_url(hass, require_standard_port=True)
            == "https://example.nabu.casa"
        )
        assert (
            async_get_url(hass, require_ssl=True, require_standard_port=True)
            == "https://example.nabu.casa"
        )

    # Test fallback to Cloud when external URL contains an IP address
    await config_util.async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://example.local:8123",
            "external_url": "https://192.168.0.1",
        },
    )
    assert hass.config.internal_url == "http://example.local:8123"
    assert hass.config.external_url == "https://192.168.0.1"

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert async_get_url(hass, require_standard_port=True) == "https://192.168.0.1"
        assert async_get_url(hass, require_ssl=True) == "https://example.nabu.casa"
        assert (
            async_get_url(hass, require_ssl=True, require_standard_port=True)
            == "https://example.nabu.casa"
        )


async def test_get_url_base_url_fallback(hass: HomeAssistant):
    """Test getting an instance URL using deprecated base_url fallback scenarios."""
    assert hass.config.internal_url is None
    assert hass.config.external_url is None

    hass.config.api = Mock(use_ssl=False, port=8123, base_url="https://www.example.com")

    assert async_get_url(hass) == "http://192.168.123.123:8123"
    assert async_get_url(hass, require_ssl=True) == "https://www.example.com"
    assert async_get_url(hass, allow_local=False) == "https://www.example.com"
    assert async_get_url(hass, require_standard_port=True) == "https://www.example.com"

    hass.config.api = Mock(
        use_ssl=False, port=8123, base_url="https://www.example.com:8123/"
    )
    assert async_get_url(hass) == "http://192.168.123.123:8123"
    assert async_get_url(hass, require_ssl=True) == "https://www.example.com:8123"
    assert async_get_url(hass, allow_local=False) == "https://www.example.com:8123"
    # Last fallback, without sanity, to `base_url`
    assert (
        async_get_url(hass, require_standard_port=True)
        == "https://www.example.com:8123"
    )

    hass.config.components.add("cloud")
    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        # Ensure without sanity fallback doesn't apply when cloud is available
        assert (
            async_get_url(hass, require_standard_port=True)
            == "https://example.nabu.casa"
        )

        # Ensure we fallback to cloud when SSL is needed but not in base_url
        hass.config.api = Mock(
            use_ssl=False, port=8123, base_url="http://www.example.com"
        )
        assert async_get_url(hass, allow_local=False) == "http://www.example.com"
        assert async_get_url(hass, require_ssl=True) == "https://example.nabu.casa"

        # Ensure we fallback to cloud when SSL is needed but not in base_url
        hass.config.api = Mock(
            use_ssl=False, port=8123, base_url="https://www.example.com:8123"
        )
        assert async_get_url(hass, allow_local=False) == "https://www.example.com:8123"
        assert async_get_url(hass, require_ssl=True) == "https://www.example.com:8123"
        assert (
            async_get_url(hass, require_ssl=True, require_standard_port=True)
            == "https://example.nabu.casa"
        )

        # With local base URL, with an IP address and SSL
        hass.config.api = Mock(use_ssl=False, port=8123, base_url="https://192.168.0.1")
        assert async_get_url(hass, allow_local=False) == "https://example.nabu.casa"
        assert async_get_url(hass, require_ssl=True) == "https://example.nabu.casa"
