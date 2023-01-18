FROM python:3.11

RUN apt-get update && apt-get -y upgrade

# libpostal
# https://github.com/openvenues/pypostal#installation
RUN apt-get install -y curl autoconf automake libtool python3-dev pkg-config
RUN git clone https://github.com/openvenues/libpostal /libpostal
WORKDIR /libpostal
RUN ./bootstrap.sh
RUN ./configure --datadir=/data/libpostal
RUN make -j2
RUN make install
RUN ldconfig

COPY ftm_geocode /app/ftm_geocode
COPY setup.py /app/setup.py
COPY setup.cfg /app/setup.cfg
COPY VERSION /app/VERSION

WORKDIR /app
RUN pip install -U pip setuptools
RUN pip install -e ".[postal]"
