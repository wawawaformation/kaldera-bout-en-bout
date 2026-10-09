FROM python:3.12-slim

WORKDIR /srv
RUN pip install --no-cache-dir "fastapi>=0.115,<0.120" "uvicorn[standard]>=0.30,<0.40" "httpx>=0.27,<0.30"
COPY . /srv/a2a_server

EXPOSE 8100
CMD ["uvicorn", "a2a_server.app:app", "--host", "0.0.0.0", "--port", "8100"]
