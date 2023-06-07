FROM python:3
COPY . /app
WORKDIR /app
RUN apt update -y && apt upgrade -y
RUN apt install openbabel -y
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "FASTAService.py", "--dev"]