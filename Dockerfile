FROM rasa/rasa:3.6.21

WORKDIR /app

USER root
COPY . /app
RUN chmod +x /app/docker/start-rasa.sh

EXPOSE 5005

USER 1001
ENTRYPOINT []
CMD ["/app/docker/start-rasa.sh"]
