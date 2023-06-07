FROM python:3
COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt
RUN apt update -y && apt upgrade -y \
    && apt install openbabel -y
RUN tar xzvf autodock_vina_1_1_2_linux_x86.tgz
CMD ["python", "DockingService.py", "--dev"]