FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CONDA_DIR=/opt/conda \
    PATH=/opt/conda/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    bzip2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p $CONDA_DIR \
    && rm /tmp/miniconda.sh \
    && conda config --set always_yes yes --set changeps1 no \
    && conda install -c bioconda busco==5.7.1 \
    && conda clean -afy

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ ./
RUN mkdir -p /app/static
COPY --from=frontend-build /app/frontend/dist /app/static

EXPOSE 7860

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
