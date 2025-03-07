FROM python:3.9-slim
WORKDIR /app

# Create a dedicated world-writable directory for data
RUN mkdir -p /data && chmod 777 /data
ENV DATA_LOCATION=/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Run as root to avoid permissions issues
EXPOSE 8501
CMD ["streamlit", "run", "main.py"]