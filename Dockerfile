FROM python:3.7

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 1337
CMD ["hypercorn", "--access-logfile", "-", "--workers", "1", "--bind", "0.0.0.0:1337", "asgi:app"]