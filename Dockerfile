FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV DATA_DIR=/data HOST=0.0.0.0 PORT=8080
VOLUME /data
EXPOSE 8080
ENV CERT_DIR=/certs
HEALTHCHECK --interval=30s --timeout=5s CMD python -m app.healthcheck || exit 1
CMD ["python", "-m", "app.main"]
