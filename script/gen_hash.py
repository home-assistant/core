#!/usr/bin/python3
"""Generate a SHA512 hash from a given string."""
import getpass
import hashlib
import uuid


def hash_password(password):
    """Create a hash of the given password"""
    salt = uuid.uuid4().hex
    return hashlib.sha512(
        salt.encode() + password.encode()).hexdigest() + ':' + salt


def check_password(hashed_password, plain_password):
    """Check the given password against the re-entered one."""
    password, salt = hashed_password.split(':')
    return password == hashlib.sha512(
        salt.encode() + plain_password.encode()).hexdigest()

response1 = getpass.getpass('Please enter your password: ')
response2 = getpass.getpass('Please enter your password again: ')

hashed = hash_password(response1)

if check_password(hashed, response2):
    print('\nPut the hash in your configuration.yaml file.')
    print(hashed)
else:
    print('No match! Please try again.')