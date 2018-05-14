"""Test the auth script to manage local users."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.scripts import auth as script_auth
from homeassistant.auth_providers import homeassistant as hass_auth

MOCK_PATH = '/bla/users.json'


def test_list_user(capsys):
    """Test we can list users."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')
    data.add_user('second-user', 'second-pass')

    script_auth.list_users(data, None)

    captured = capsys.readouterr()

    assert captured.out == '\n'.join([
        'test-user',
        'second-user',
        '',
        'Total users: 2',
        ''
    ])


def test_add_user(capsys):
    """Test we can add a user."""
    data = hass_auth.Data(MOCK_PATH, None)

    with patch.object(data, 'save') as mock_save:
        script_auth.add_user(
            data, Mock(username='paulus', password='test-pass'))

    assert len(mock_save.mock_calls) == 1

    captured = capsys.readouterr()
    assert captured.out == 'User created\n'

    assert len(data.users) == 1
    data.validate_login('paulus', 'test-pass')


def test_validate_login(capsys):
    """Test we can validate a user login."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')

    script_auth.validate_login(
        data, Mock(username='test-user', password='test-pass'))
    captured = capsys.readouterr()
    assert captured.out == 'Auth valid\n'

    script_auth.validate_login(
        data, Mock(username='test-user', password='invalid-pass'))
    captured = capsys.readouterr()
    assert captured.out == 'Auth invalid\n'

    script_auth.validate_login(
        data, Mock(username='invalid-user', password='test-pass'))
    captured = capsys.readouterr()
    assert captured.out == 'Auth invalid\n'


def test_change_password(capsys):
    """Test we can change a password."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')

    with patch.object(data, 'save') as mock_save:
        script_auth.change_password(
            data, Mock(username='test-user', new_password='new-pass'))

    assert len(mock_save.mock_calls) == 1
    captured = capsys.readouterr()
    assert captured.out == 'Password changed\n'
    data.validate_login('test-user', 'new-pass')
    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('test-user', 'test-pass')


def test_change_password_invalid_user(capsys):
    """Test changing password of non-existing user."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')

    with patch.object(data, 'save') as mock_save:
        script_auth.change_password(
            data, Mock(username='invalid-user', new_password='new-pass'))

    assert len(mock_save.mock_calls) == 0
    captured = capsys.readouterr()
    assert captured.out == 'User not found\n'
    data.validate_login('test-user', 'test-pass')
    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('invalid-user', 'new-pass')
