ARG BASE_IMAGE=ghcr.io/home-assistant/home-assistant:beta
FROM $BASE_IMAGE

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY entrypoint.sh /entrypoint.sh

RUN \
    uv pip install stdlib-list==0.10.0 \
        $(grep -e "^pipdeptree" -e "^tqdm" /usr/src/homeassistant/requirements_test.txt) \
        $(grep -e "^ruff" /usr/src/homeassistant/requirements_test_pre_commit.txt)

WORKDIR "/github/workspace"
ENTRYPOINT ["/entrypoint.sh"]

LABEL "name"="hassfest"
LABEL "maintainer"="Home Assistant <hello@home-assistant.io>"

LABEL "com.github.actions.name"="hassfest"
LABEL "com.github.actions.description"="Run hassfest to validate standalone integration repositories"
LABEL "com.github.actions.icon"="terminal"
LABEL "com.github.actions.color"="gray-dark"
