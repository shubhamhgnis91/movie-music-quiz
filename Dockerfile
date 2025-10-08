FROM python:3.11-slim

WORKDIR /code

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application code
COPY ./app /code/app
COPY ./static /code/static
COPY ./main.py /code/main.py
COPY ./top500.csv /code/top500.csv

# Create directory for database
RUN mkdir -p /code/data

# Expose port
EXPOSE 8000

# Run with single process (cluster handles replication)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
