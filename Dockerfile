FROM python:3.9.10-buster

WORKDIR /app
COPY . .

RUN pip3 --no-cache-dir install -r requirements.txt

EXPOSE 5000

ENTRYPOINT ["python3"]
CMD ["app.py"]
