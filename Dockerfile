FROM python:3.8-slim-buster

WORKDIR /geddit

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

RUN mkdir shared

CMD = ["python3", "-m", "main.py"]