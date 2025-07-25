# syntax=docker/dockerfile:1.4
FROM ubuntu:latest


WORKDIR /app


RUN apt update
RUN apt install python3 python3-pip -y

RUN apt-get install apt-transport-https ca-certificates gnupg curl -y
RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
RUN apt-get update && apt-get install google-cloud-cli -y

COPY app/gcloud_keys.json .
RUN gcloud auth activate-service-account --key-file=gcloud_keys.json
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/gcloud_keys.json

COPY app/requirements.txt .
RUN pip3 install -r requirements.txt --break-system-packages


ENTRYPOINT ["/app/startup.sh"]
