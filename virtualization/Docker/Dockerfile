FROM alpine:3.4

ENV HASS_VERSION 0.27.1

RUN apk add --update python3-dev curl libffi-dev build-base openssl-dev linux-headers \
  && curl -O https://bootstrap.pypa.io/get-pip.py \
  && python3 get-pip.py \
  && curl -L -O https://github.com/home-assistant/home-assistant/archive/${HASS_VERSION}.tar.gz \
  && tar xfvz ${HASS_VERSION}.tar.gz \
  && cd home-assistant-${HASS_VERSION} \
  && pip install -r requirements_all.txt
