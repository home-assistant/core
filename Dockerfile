FROM python:3.4
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN pip3 install --no-cache-dir colorlog

# For the nmap tracker
RUN apt-get update && \
    apt-get install -y --no-install-recommends nmap net-tools && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY script/build_python_openzwave script/build_python_openzwave
RUN apt-get update && \
   apt-get install -y cython3 libudev-dev && \
   apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
   pip3 install "cython<0.23" && \
   script/build_python_openzwave

COPY requirements_all.txt requirements_all.txt
RUN pip3 install --no-cache-dir -r requirements_all.txt

# Copy source
COPY . .

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
