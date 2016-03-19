#!/usr/bin/python3
"""Generate hashes from given strings."""
import getpass
from passlib import hash

response1 = getpass.getpass('Please enter your string/password/API key: ')
response2 = getpass.getpass('Please enter the string/password/API key again: ')

hashed = hash.sha256_crypt.encrypt(response1)

if hash.sha256_crypt.verify(response2, hashed):
    print('Put the hash in your configuration.yaml file.')
    print(hashed)
else:
    print('No match! Please try again.')
