FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .


RUN useradd -m appuser && chown -R appuser /app


USER appuser

# Expose Streamlit port
EXPOSE 8501

# Command to run the application
CMD ["streamlit", "run", "main.py"]