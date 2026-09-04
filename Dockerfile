FROM apache/superset:latest
USER root
RUN /app/.venv/bin/python3 -m ensurepip --upgrade && \
    /app/.venv/bin/python3 -m pip install --no-cache-dir psycopg2-binary
USER superset