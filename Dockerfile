FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

RUN apt-get update && \
    apt-get install -y cython3 libudev-dev python-sphinx python3-setuptools mercurial && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    pip3 install cython && \
    cd .. && \
    git clone https://github.com/Artanis/louie.git && \
    cd louie && \
    python setup.py install && \
    cd .. && \
    hg clone https://code.google.com/p/python-openzwave/ && \
    cd python-openzwave && \
    ./update.sh && \
    sed -i '253s/.*//' openzwave/cpp/src/value_classes/ValueID.h && \
    2to3 --no-diffs -w -n api examples && \
    ./compile.sh && \
    ./install.sh

# L18 sed is to apply a patch to make openzwave compile
# L19 2to3 to have the api code work in Python 3

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
