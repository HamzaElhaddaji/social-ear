FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000
WORKDIR /srv/social-ear
ARG INSTALL_MODELS=0
COPY requirements.txt requirements-models.txt ./
RUN if [ "$INSTALL_MODELS" = "1" ]; then pip install --no-cache-dir -r requirements-models.txt; else pip install --no-cache-dir -r requirements.txt; fi
RUN groupadd --gid 10001 socialear && useradd --uid 10001 --gid socialear --create-home socialear
COPY app app
COPY web web
RUN mkdir data && chown socialear:socialear data
USER socialear
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["python", "-m", "app"]
