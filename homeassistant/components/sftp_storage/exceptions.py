"""SFTP Storage integration exceptions."""


class SFTPStorageException(Exception):
    """Base exception for SFTP Storage integration."""


class SFTPStorageInvalidPrivateKey(SFTPStorageException):
    """Exception raised during config flow - when user provided invalid private key file."""


class SFTPStorageMissingPasswordOrPkey(SFTPStorageException):
    """Exception raised during config flow - when user did not provide password or private key file."""
