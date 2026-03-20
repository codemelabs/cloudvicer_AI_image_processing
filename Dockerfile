# Use official Python 3.10 image
FROM python:3.10.8-slim

# Set working directory
WORKDIR /app

# Copy files
COPY . /app

# Install dependencies (if you have requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (change if needed)
EXPOSE 5001

# Run your app
CMD ["python", "app.py"]
