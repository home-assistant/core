ARG BUILD_FROM
FROM ${BUILD_FROM}

# Synchronize with homeassistant/core.py:async_stop
ENV \
    S6_SERVICES_GRACETIME=220000

WORKDIR /usr/src

## Setup Home Assistant
COPY . homeassistant/
RUN \
    pip3 install --no-cache-dir --no-index --only-binary=:all: --find-links "${WHEELS_LINKS}" \
    -r homeassistant/requirements_all.txt \
    && pip3 install --no-cache-dir --no-index --only-binary=:all: --find-links "${WHEELS_LINKS}" \
    -e ./homeassistant \
    && python3 -m compileall homeassistant/homeassistant

# Fix Bug with Alpine 3.14 and sqlite 3.35
ARG BUILD_ARCH
RUN \
    curl -O http://dl-cdn.alpinelinux.org/alpine/v3.13/main/${BUILD_ARCH}/sqlite-libs-3.34.1-r0.apk \
    && apk add sqlite-libs-3.34.1-r0.apk \
    && rm -f sqlite-libs-3.34.1-r0.apk

# Home Assistant S6-Overlay
COPY rootfs /

WORKDIR /config
