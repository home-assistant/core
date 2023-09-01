# pytest ./tests/components/flexmeasures/ --cov=homeassistant.components.flexmeasures --cov-report term-missing -vv


from homeassistant.components.flexmeasures.const import DOMAIN
from homeassistant.components.flexmeasures.services import SERVICES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_load_unload_config_entry(
    hass: HomeAssistant, setup_fm_integration
) -> None:
    """Test setup of integration."""

    entry = setup_fm_integration

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service["service"])

    assert entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    for service in SERVICES:
        assert not hass.services.has_service(DOMAIN, service["service"])

    assert entry.state == ConfigEntryState.NOT_LOADED

    # assert not hass.data.get(DOMAIN)
