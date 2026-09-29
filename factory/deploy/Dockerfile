# Live demo image: the band's stage image, built unchanged from its own Dockerfile, plus the
# demo front door (proxy.py) that closes the test endpoints and reseeds the demo accounts.
#   docker build -t app stage-4
#   docker build -t demo --build-arg APP_IMAGE=app --build-arg APP_CMD="python -m app.main" factory/deploy
ARG APP_IMAGE
FROM ${APP_IMAGE}
ARG APP_CMD
ENV DEMO_APP_CMD=${APP_CMD} DEMO_UPSTREAM_PORT=8081 DEMO_RESET_SECONDS=3600 PORT=10000
COPY proxy.py seed.json /demo/
EXPOSE 10000
CMD ["python3", "/demo/proxy.py"]
