from kombu import Connection, Exchange, Queue, Producer
from kombu.mixins import ConsumerProducerMixin
import json
from time import sleep
from random import uniform
from FASTAGenerator import FASTAGenerator
import logging
import yaml
import argparse

def initialize_logging(mod_name):
    logger = logging.getLogger(mod_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger

def createResultMessage(id: str, fasta: str):
    message = {
        "message": {
            "id": id,
            "FASTA": fasta
        },
        "messageType": [
            "urn:message:AsyncAPI.Models:FASTAResult"
        ]
    }
    return message

class Worker(ConsumerProducerMixin):
    def __init__(self, connection, queues, config):
        self.connection = connection
        self.queues = queues
        self.logger = initialize_logging("FASTAService")
        self.config = config

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=self.queues, callbacks=[self.on_message])]

    def on_message(self, body, message):
        generator = FASTAGenerator(self.config)
        self.logger.info(f"Received message {body}")
        result = createResultMessage(body["id"], generator.getFASTA(body["path"]))
        self.logger.info(f"Publishing result for message {body}")
        self.producer.publish(
            json.dumps(result), exchange="AsyncAPI.Models:FASTAResult", retry=True
        )
        message.ack()

def setup_mq(host):
    connection = Connection(host, heartbeat=20)
    channel = connection.channel()
    exchange = Exchange("AsyncAPI.Models:FASTAResult", "fanout", channel=channel)
    exchange.declare()

    Queue("FASTAResult", exchange=exchange, channel=channel).declare()

    return connection, channel, exchange


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="FASTAService",
        description="Gets FASTA for a given pdb(qt) file"
    )
    parser.add_argument("--dev", action="store_true", help="Use config_dev.yml")
    args =  parser.parse_args()

    config = None
    if args.dev:
        with open("config_dev.yml", 'r') as f:
            config = yaml.safe_load(f)
    else:
        with open("config.yml", 'r') as f:
            config = yaml.safe_load(f)

    connection, channel, exchange = setup_mq(config["service"]["rabbitmq"])

    worker = Worker(connection,
                    [Queue("FASTATask",
                     exchange=Exchange("AsyncAPI.Models:FASTATask", "fanout"))],
                    config)
    worker.run()
