"""Test the Emulated Hue component."""
from unittest.mock import patch, Mock, MagicMock

from homeassistant.components.emulated_hue import Config


def test_config_google_home_entity_id_to_number():
    """Test config adheres to the type."""
    mock_hass = Mock()
    mock_hass.config.path = MagicMock("path", return_value="test_path")
    conf = Config(mock_hass, {
        'type': 'google_home'
    })

    with patch('homeassistant.components.emulated_hue.load_json',
               return_value={'1': 'light.test2'}) as json_loader:
        with patch('homeassistant.components.emulated_hue'
                   '.save_json') as json_saver:
            number = conf.entity_id_to_number('light.test')
            assert number == '2'

            assert json_saver.mock_calls[0][1][1] == {
                '1': 'light.test2', '2': 'light.test'
            }

            assert json_saver.call_count == 1
            assert json_loader.call_count == 1

            number = conf.entity_id_to_number('light.test')
            assert number == '2'
            assert json_saver.call_count == 1

            number = conf.entity_id_to_number('light.test2')
            assert number == '1'
            assert json_saver.call_count == 1

            entity_id = conf.number_to_entity_id('1')
            assert entity_id == 'light.test2'


def test_config_google_home_entity_id_to_number_altered():
    """Test config adheres to the type."""
    mock_hass = Mock()
    mock_hass.config.path = MagicMock("path", return_value="test_path")
    conf = Config(mock_hass, {
        'type': 'google_home'
    })

    with patch('homeassistant.components.emulated_hue.load_json',
               return_value={'21': 'light.test2'}) as json_loader:
        with patch('homeassistant.components.emulated_hue'
                   '.save_json') as json_saver:
            number = conf.entity_id_to_number('light.test')
            assert number == '22'
            assert json_saver.call_count == 1
            assert json_loader.call_count == 1

            assert json_saver.mock_calls[0][1][1] == {
                '21': 'light.test2',
                '22': 'light.test',
            }

            number = conf.entity_id_to_number('light.test')
            assert number == '22'
            assert json_saver.call_count == 1

            number = conf.entity_id_to_number('light.test2')
            assert number == '21'
            assert json_saver.call_count == 1

            entity_id = conf.number_to_entity_id('21')
            assert entity_id == 'light.test2'


def test_config_google_home_entity_id_to_number_empty():
    """Test config adheres to the type."""
    mock_hass = Mock()
    mock_hass.config.path = MagicMock("path", return_value="test_path")
    conf = Config(mock_hass, {
        'type': 'google_home'
    })

    with patch('homeassistant.components.emulated_hue.load_json',
               return_value={}) as json_loader:
        with patch('homeassistant.components.emulated_hue'
                   '.save_json') as json_saver:
            number = conf.entity_id_to_number('light.test')
            assert number == '1'
            assert json_saver.call_count == 1
            assert json_loader.call_count == 1

            assert json_saver.mock_calls[0][1][1] == {
                '1': 'light.test',
            }

            number = conf.entity_id_to_number('light.test')
            assert number == '1'
            assert json_saver.call_count == 1

            number = conf.entity_id_to_number('light.test2')
            assert number == '2'
            assert json_saver.call_count == 2

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
