"""Test cases for digital_ocean integration initialization."""
import digitalocean

from homeassistant.components.digital_ocean import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_digital_ocean_init(
    hass: HomeAssistant, digital_ocean_config, digital_ocean_account
) -> None:
    """Test case for the successful initialization of this integration."""
    result = await async_setup_component(hass, DOMAIN, digital_ocean_config)
    await hass.async_block_till_done()

    assert result is True, "Failed configuring Digital Ocean"
    digital_ocean_account.assert_called_once()

    assert hass.services.has_service(
        DOMAIN, "update_domain_record"
    ), "DNS service not registered"


async def test_digital_ocean_init_failed_account(
    hass: HomeAssistant, digital_ocean_config, digital_ocean_account
) -> None:
    """Test case for the failed integration bootstrap - No account found."""
    digital_ocean_account.return_value = None

    result = await async_setup_component(hass, DOMAIN, digital_ocean_config)
    await hass.async_block_till_done()

    assert result is False, "Digital Ocean config was OK"
    digital_ocean_account.assert_called_once()

    assert not hass.services.has_service(
        DOMAIN, "update_domain_record"
    ), "DNS service was registered"


async def test_digital_ocean_init_failed_account_request(
    hass: HomeAssistant, digital_ocean_config, digital_ocean_account
) -> None:
    """Test case for the failed integration bootstrap - Request Error."""
    digital_ocean_account.side_effect = digitalocean.baseapi.DataReadError()

    result = await async_setup_component(hass, DOMAIN, digital_ocean_config)
    await hass.async_block_till_done()

    assert result is False, "Digital Ocean config was OK"
    digital_ocean_account.assert_called_once()

    assert not hass.services.has_service(
        DOMAIN, "update_domain_record"
    ), "DNS service was registered"
