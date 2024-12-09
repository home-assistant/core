import copy
import os
from typing import Dict, Optional, Sequence
import typing
import keyring

from .exceptions import PyiCloudNoStoredPasswordAvailableException

KEYRING_SYSTEM = 'pyicloud://icloud-password'

def password_exists_in_keyring(username:str) -> bool:
    try:
        return get_password_from_keyring(username) is not None
    except PyiCloudNoStoredPasswordAvailableException:
        return False


def get_password_from_keyring(username:str) -> Optional[str]:
    result = keyring.get_password(
        KEYRING_SYSTEM,
        username
    )

    return result


def store_password_in_keyring(username: str, password:str) -> None:
    # if get_password_from_keyring(username) is not None:
    #     # Apple can save only into empty keyring
    #     return delete_password_in_keyring(username)
    return keyring.set_password(
        KEYRING_SYSTEM,
        username,
        password,
    )


def delete_password_in_keyring(username:str) -> None:
    return keyring.delete_password(
        KEYRING_SYSTEM,
        username,
    )


def underscore_to_camelcase(word:str , initial_capital: bool=False) -> str:
    words = [x.capitalize() or '_' for x in word.split('_')]
    if not initial_capital:
        words[0] = words[0].lower()

    return ''.join(words)