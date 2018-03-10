"""Test the Emulated Hue component."""
import json

from unittest.mock import patch, Mock, mock_open

from homeassistant.components.emulated_hue import Config, _LOGGER


def test_config_google_home_entity_id_to_number():
    """Test config adheres to the type."""
    conf = Config(Mock(), {
        'type': 'google_home'
    })

    mop = mock_open(read_data=json.dumps({'1': 'light.test2'}))
    handle = mop()

    with patch('homeassistant.util.json.open', mop, create=True):
        number = conf.entity_id_to_number('light.test')
        assert number == '2'
        assert handle.write.call_count == 1
        assert json.loads(handle.write.mock_calls[0][1][0]) == {
            '1': 'light.test2',
            '2': 'light.test',
        }

        number = conf.entity_id_to_number('light.test')
        assert number == '2'
        assert handle.write.call_count == 1

        number = conf.entity_id_to_number('light.test2')
        assert number == '1'
        assert handle.write.call_count == 1

        entity_id = conf.number_to_entity_id('1')
        assert entity_id == 'light.test2'


def test_config_google_home_entity_id_to_number_altered():
    """Test config adheres to the type."""
    conf = Config(Mock(), {
        'type': 'google_home'
    })

    mop = mock_open(read_data=json.dumps({'21': 'light.test2'}))
    handle = mop()

    with patch('homeassistant.util.json.open', mop, create=True):
        number = conf.entity_id_to_number('light.test')
        assert number == '22'
        assert handle.write.call_count == 1
        assert json.loads(handle.write.mock_calls[0][1][0]) == {
            '21': 'light.test2',
            '22': 'light.test',
        }

        number = conf.entity_id_to_number('light.test')
        assert number == '22'
        assert handle.write.call_count == 1

        number = conf.entity_id_to_number('light.test2')
        assert number == '21'
        assert handle.write.call_count == 1

        entity_id = conf.number_to_entity_id('21')
        assert entity_id == 'light.test2'


def test_config_google_home_entity_id_to_number_empty():
    """Test config adheres to the type."""
    conf = Config(Mock(), {
        'type': 'google_home'
    })

    mop = mock_open(read_data='')
    handle = mop()

    with patch('homeassistant.util.json.open', mop, create=True):
        number = conf.entity_id_to_number('light.test')
        assert number == '1'
        assert handle.write.call_count == 1
        assert json.loads(handle.write.mock_calls[0][1][0]) == {
            '1': 'light.test',
        }

        number = conf.entity_id_to_number('light.test')
        assert number == '1'
        assert handle.write.call_count == 1

        number = conf.entity_id_to_number('light.test2')
        assert number == '2'
        assert handle.write.call_count == 2

        entity_id = conf.number_to_entity_id('2')
        assert entity_id == 'light.test2'


def test_config_alexa_entity_id_to_number():
    """Test config adheres to the type."""
    conf = Config(None, {
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
        Config(None, {
            'type': 'google_home',
            'host_ip': '123.123.123.123',
            'listen_port': 8300
        })

        assert mock_warn.called
        assert mock_warn.mock_calls[0][1][0] == \
            "When targeting Google Home, listening port has to be port 80"
