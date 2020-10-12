FROM python:3.7-alpine
RUN apk add --no-cache gcc musl-dev linux-headers
WORKDIR /var/www
ENV FLASK_APP app.py
ENV FLASK_RUN_HOST 0.0.0.0
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
EXPOSE 5000
COPY app.py app.py
COPY *.html templates/
copy *.pem ./
CMD ["sh", "-c", "flask run --cert=cert.pem --key=key.pem"]