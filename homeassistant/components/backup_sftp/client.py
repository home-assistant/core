import re
from pathlib import Path

import paramiko

from homeassistant.exceptions import ConfigEntryError


class SSHClient(paramiko.SSHClient):
    """
    Derrived class from `paramiko.SSHClient` - allowing for automatic SSH connection establishment
    and proper error handling.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str = "",
        private_key_file: str = "",
        backup_location: str = "",
    ):
        super().__init__()
        self.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy)
        self._host = host
        self._port = port
        self._username = username
        self._backup_location = backup_location

        if private_key_file:
            # Check if private key exists.
            if not Path(private_key_file).exists():
                raise ConfigEntryError(
                    f'Configured Private key file for SFTP Backup Storage not found at "{private_key_file}".'
                )

            key = paramiko.RSAKey.from_private_key_file(private_key_file)

            # Attempt connection via private key file.
            try:
                self.connect(hostname=host, port=port, username=username, pkey=key)
            except paramiko.AuthenticationException as e:
                raise ConfigEntryError(
                    f"Unable to connect to {username}@{host}:{port} using private key. Please check that you've used correct key. {e}"
                )
            except Exception as e:
                raise ConfigEntryError(
                    f"Unable to connect to {username}@{host}:{port} using private key due to exception {type(e).__name__}. {e}"
                )

        elif password:
            # Attempt connection via username, password.
            try:
                self.connect(
                    hostname=host, port=port, username=username, password=password
                )
            except paramiko.AuthenticationException as e:
                raise ConfigEntryError(
                    f"Unable to connect to {username}@{host}:{port} using password. Please check your credentials. {e}"
                )
            except Exception as e:
                raise ConfigEntryError(
                    f"Unable to connect to {username}@{host}:{port} using password authentication due to exception {type(e).__name__}. {e}"
                )

        else:
            raise ConfigEntryError(
                f"Please configure password or private key file location for SFTP Backup Storage."
            )

    def get_identifier(self) -> str:
        """
        Returns unique identifier that consists of:
        `backup_sftp.<host>.<port>.<username>.<remote_path>`.
        `remote_path` has all non-alphanumeric characters replaced by `_`, as well as `host`
        and `username`.


        Example
        ----------
        >>> client = SSHClient(host='192.168.0.100', port=22, username='user', password='S3c5e7p@sSw0rD', backup_location='/mnt/backup_storage')
        >>> client.get_identifier()
        'backup_sftp.192_168_0_100.22.user.mnt_backup_storage'
        """

        host = re.sub(r"[^a-zA-Z\d\s:]", "_", self._host)
        remote_path = re.sub(r"[^a-zA-Z\d\s:]", "_", self._backup_location)
        user = re.sub(r"[^a-zA-Z\d\s:]", "_", self._username)

        return f"backup_sftp.{host}.{self._port}.{user}.{remote_path}"
