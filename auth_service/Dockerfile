FROM python:3.10
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY auth_main.py ./
EXPOSE 5001
CMD ["python", "auth_main.py"]