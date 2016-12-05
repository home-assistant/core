from unittest.mock import patch

from homeassistant.components.emulated_hue import Config, _LOGGER


def test_config_google_home_entity_id_to_number():
    """Test config adheres to the type."""
    conf = Config({
        'type': 'google_home'
    })

    number = conf.entity_id_to_number('light.test')
    assert number == '1'

    number = conf.entity_id_to_number('light.test')
    assert number == '1'

    number = conf.entity_id_to_number('light.test2')
    assert number == '2'

    entity_id = conf.number_to_entity_id('1')
    assert entity_id == 'light.test'


def test_config_alexa_entity_id_to_number():
    """Test config adheres to the type."""
    conf = Config({
        'type': 'alexa'
    })

    number = conf.entity_id_to_number('light.test')
    assert number == 'light.test'

    number = conf.entity_id_to_number('light.test')
    assert number == 'light.test'

    number = conf.entity_id_to_number('light.test2')
    assert number == 'light.test2'

    entity_id = conf.number_to_entity_id('light.test')
    assert entity_id == 'light.test'


def test_warning_config_google_home_listen_port():
    """Test we warn when non-default port is used for Google Home."""
    with patch.object(_LOGGER, 'warning') as mock_warn:
        Config({
            'type': 'google_home',
            'host_ip': '123.123.123.123',
            'listen_port': 8300
        })

        assert mock_warn.called
        assert mock_warn.mock_calls[0][1][0] == \
            "When targetting Google Home, listening port has to be port 80"
