FROM alpine:latest
COPY requirements.txt /app/requirements.txt
RUN apk --update add python3 \
    && apk add py3-pip \
    && rm -f /var/cache/apk/* \
    && pip3 install --upgrade pip \
    && pip3 install --upgrade setuptools \
    && pip3 uninstall $(pip freeze) -y \
    && pip3 install -r /app/requirements.txt \
    && apk add py3-pandas
COPY checker.py /usr/bin/checker
RUN chmod +x /usr/bin/checker
ENTRYPOINT /bin/ash