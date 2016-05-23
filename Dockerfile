FROM python:3.4-alpine
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN apk update && apk upgrade && apk add git coreutils perl openssl nmap net-tools cython sudo

RUN cd / && \
    mkdir build && \
    cd build && \
    git clone --recursive https://github.com/OpenZWave/python-openzwave.git && \
    cd python-openzwave && \
    git checkout python3 && \
    git clone git://github.com/OpenZWave/open-zwave.git openzwave

RUN apk add build-base linux-headers eudev-dev glib-dev

RUN pip3 install --upgrade --no-cache-dir colorlog cython pip

RUN cd /build/python-openzwave && \
    PYTHON_EXEC=`which python3` make build && \
    PYTHON_EXEC=`which python3` make install

RUN mkdir -p /usr/local/share/python-openzwave && \
    ln -sf /build/python-openzwave/openzwave/config /usr/local/share/python-openzwave/config

COPY requirements_all.txt requirements_all.txt
RUN pip3 install --no-cache-dir -r requirements_all.txt

RUN apk del build-base linux-headers eudev-dev glib-dev && \
    rm -rf /tmp/* /var/tmp/*

# Copy source
COPY . .

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
