ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim


WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -r /app/requirements.txt

COPY . /app

ENV PORT=8000
EXPOSE 8000

# Use exec form so arguments are literal and not affected by shell/env expansion
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]