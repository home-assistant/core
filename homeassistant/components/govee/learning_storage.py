"""The Govee learned storage yaml file manager."""

from dataclasses import asdict
import logging

import dacite
from govee_api_laggat import GoveeAbstractLearningStorage, GoveeLearnedInfo
import yaml

from homeassistant.util.yaml import load_yaml, save_yaml

_LOGGER = logging.getLogger(__name__)
LEARNING_STORAGE_YAML = "/govee_learning.yaml"


class GoveeLearningStorage(GoveeAbstractLearningStorage):
    """The govee_api_laggat library uses this to store learned information about led strips."""

    def __init__(self, config_dir, *args, **kwargs):
        """Get the config directory."""
        super().__init__(*args, **kwargs)
        self._config_dir = config_dir

    async def read(self):
        """Restore from yaml file."""
        learned_info = {}
        try:
            learned_dict = load_yaml(self._config_dir + LEARNING_STORAGE_YAML)
            learned_info = {
                device: dacite.from_dict(
                    data_class=GoveeLearnedInfo, data=learned_dict[device]
                )
                for device in learned_dict
            }
            _LOGGER.info(
                "Loaded learning information from %s.",
                self._config_dir + LEARNING_STORAGE_YAML,
            )
        except FileNotFoundError:
            _LOGGER.warning(
                "There is no %s file containing learned information about your devices. This is normal for first start of Govee integration.",
                self._config_dir + LEARNING_STORAGE_YAML,
            )
        except (
            dacite.DaciteError,
            TypeError,
            UnicodeDecodeError,
            yaml.YAMLError,
        ) as ex:
            _LOGGER.warning(
                "The %s file containing learned information about your devices is invalid: %s. Learning starts from scratch.",
                self._config_dir + LEARNING_STORAGE_YAML,
                ex,
            )
        return learned_info

    async def write(self, learned_info):
        """Save to yaml file."""
        leaned_dict = {device: asdict(learned_info[device]) for device in learned_info}
        save_yaml(self._config_dir + LEARNING_STORAGE_YAML, leaned_dict)
        _LOGGER.info(
            "Stored learning information to %s.",
            self._config_dir + LEARNING_STORAGE_YAML,
        )
