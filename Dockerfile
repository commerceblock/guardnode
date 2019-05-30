FROM python:3.7.3

COPY . /usr/src

ENV PATH=$PATH:/usr/src

RUN set -x \
    && cd /usr/src \
    && pip install -r requirements.txt \
    && python setup.py build \
    && python setup.py install

CMD ["bash", "-c"]
