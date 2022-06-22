ARG BUILD_FROM
FROM ${BUILD_FROM}

# Synchronize with homeassistant/core.py:async_stop
ENV \
    S6_SERVICES_GRACETIME=220000

WORKDIR /usr/src

## Setup Home Assistant Core dependencies
COPY requirements.txt homeassistant/
COPY homeassistant/package_constraints.txt homeassistant/homeassistant/
# hadolint ignore=DL4006
RUN \ 
   grep -v '^[#-]' < homeassistant/requirements.txt | xargs -P 6 -n 4 -- \
   pip3 download --no-index --only-binary=:all: \
   --find-links "${WHEELS_LINKS}" --use-deprecated=legacy-resolver \
   --cache-dir "/tmp/pip_cache" ; exit 0
RUN \
    pip3 install --cache-dir "/tmp/pip_cache" --no-index --only-binary=:all: --find-links "${WHEELS_LINKS}" \
    -r homeassistant/requirements.txt --use-deprecated=legacy-resolver
COPY requirements_all.txt homeassistant/
# hadolint ignore=DL4006
RUN \ 
   grep -v '^[#-]' < homeassistant/requirements_all.txt | xargs -P 8 -n 120 -- \
   pip3 download --no-index --only-binary=:all: \
   --find-links "${WHEELS_LINKS}" --use-deprecated=legacy-resolver \
   --cache-dir "/tmp/pip_cache" ; exit 0
RUN \
    pip3 install --cache-dir "/tmp/pip_cache" --no-index --only-binary=:all: --find-links "${WHEELS_LINKS}" \
    -r homeassistant/requirements_all.txt --use-deprecated=legacy-resolver

RUN rm -rf /tmp/pip_cache

## Setup Home Assistant Core
COPY . homeassistant/
RUN \
    pip3 install --no-cache-dir --no-index --only-binary=:all: --find-links "${WHEELS_LINKS}" \
    -e ./homeassistant --use-deprecated=legacy-resolver \
    && python3 -m compileall homeassistant/homeassistant

# Home Assistant S6-Overlay
COPY rootfs /

WORKDIR /config
