FROM python:3.10

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY transaction_main.py ./

EXPOSE 5002

CMD ["python", "transaction_main.py"]
