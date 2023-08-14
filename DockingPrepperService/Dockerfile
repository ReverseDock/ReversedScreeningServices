FROM continuumio/anaconda3
COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt
RUN apt update -y && apt upgrade -y \
    && apt install openbabel -y
RUN tar xzvf mgltools_x86_64Linux2_1.5.7p1.tar.gz \
    && mkdir ./mgltools_bin \
    && cd ./mgltools_x86_64Linux2_1.5.7 \
    && ./install.sh -d ../mgltools_bin \
    && rm -rf ../mgltools_x86_64Linux2_1.5.7
RUN conda install -c conda-forge gcc=12.1.0 openmm numpy pdbfixer
CMD ["python", "DockingPrepperService.py", "--dev"]