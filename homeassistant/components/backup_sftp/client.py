from pathlib import Path

import paramiko

from homeassistant.components.backup.agent import BackupAgentError


class SSHClient(paramiko.SSHClient):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str = "",
        private_key_file: str = "",
    ):
        super().__init__()
        self.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy)

        if private_key_file:
            # Check if private key exists.
            if not Path(private_key_file).exists():
                raise BackupAgentError(
                    f'Configured Private key file for SFTP Backup Storage not found at "{private_key_file}".'
                )

            key = paramiko.RSAKey.from_private_key_file(private_key_file)

            # Attempt connection via private key file.
            try:
                self.connect(hostname=host, port=port, username=username, pkey=key)
            except Exception as e:
                raise BackupAgentError(
                    f"Unable to connect to {username}@{host}:{port} using private key due to exception {type(e).__name__}. {e}"
                )

        elif password:
            # Attempt connection via username, password.
            try:
                self.connect(
                    hostname=host, port=port, username=username, password=password
                )
            except Exception as e:
                raise BackupAgentError(
                    f"Unable to connect to {username}@{host}:{port} using password authentication due to exception {type(e).__name__}. {e}"
                )

        else:
            raise BackupAgentError(
                f"Please configure password or private key file location for SFTP Backup Storage."
            )
