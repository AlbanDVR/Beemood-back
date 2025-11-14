ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

ENV HOST=0.0.0.0 \
    PORT=8000 \
    APP_MODULE=app.main:app


WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && if [ -s /app/requirements.txt ]; then pip install -r /app/requirements.txt; fi

COPY . /app

EXPOSE 8000

CMD uvicorn ${APP_MODULE} --host ${HOST} --port ${PORT} --reload