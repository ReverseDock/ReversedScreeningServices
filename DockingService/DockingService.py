import datetime
from kombu import Connection, Exchange, Queue, Producer
from kombu.mixins import ConsumerProducerMixin
import json
from time import time
from random import uniform
import math
from Docker import Docker
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

def createResultMessage(submission: str, receptor: str, affinity: float, outputDir: str, secondsToCompletion: int, success: bool, timeOut: bool = False):
    message = {
        "message": {
            "submission": submission,
            "receptor": receptor,
            "affinity": affinity,
            "outputPath": outputDir,
            "secondsToCompletion": secondsToCompletion,
            "success": success,
            "timeOut": timeOut
        },
        "messageType": [
            "urn:message:AsyncAPI.Models:DockingResult"
        ]
    }
    return message

class Worker(ConsumerProducerMixin):
    def __init__(self, connection, queues, config):
        self.connection = connection
        self.queues = queues
        self.logger = initialize_logging("DockingService")
        self.config = config

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=self.queues, callbacks=[self.on_message], prefetch_count=1)]

    def on_message(self, body, message):
        docker = Docker(self.config)
        self.logger.info(f"Received message {body}")
        published_at = datetime.datetime.strptime(body["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
        start_time = time()
    
        # Check that message is not older than 48 hours
        if (datetime.datetime.utcnow() - published_at).total_seconds() > 48 * 60 * 60:
            self.logger.info("Message is too old, discarding")
            message.reject(requeue=False)
            elapsed_time = math.ceil(time() - start_time)
            result = createResultMessage(body["submissionId"], body["receptorId"], 0, "", elapsed_time, False, True)
            self.producer.publish(
                json.dumps(result), exchange="AsyncAPI.Models:DockingResult", retry=True
            )
            return

        try:
            affinity, outputdir = docker.runDocking(body["ligandPath"], body["receptorPath"], body["configPath"], body["exhaustiveness"])
        except Exception:
            message.reject(requeue=False)
            elapsed_time = math.ceil(time() - start_time)
            result = createResultMessage(body["submissionId"], body["receptorId"], 0, "", elapsed_time, False)
            self.producer.publish(
                json.dumps(result), exchange="AsyncAPI.Models:DockingResult", retry=True
            )
            return

        elapsed_time = math.ceil(time() - start_time)
        self.logger.info(f"Docking took {elapsed_time} seconds")
        result = createResultMessage(body["submissionId"], body["receptorId"], affinity, outputdir, elapsed_time, True)
        self.logger.info(f"Publishing result {json.dumps(result)}")
        self.producer.publish(
            json.dumps(result), exchange="AsyncAPI.Models:DockingResult", retry=True
        )
        message.ack()

def setup_mq(host):
    connection = Connection(host, heartbeat=0)
    channel = connection.channel()
    exchange = Exchange("AsyncAPI.Models:DockingResult", "fanout", channel=channel)
    exchange.declare()

    Queue("DockingResult", exchange=exchange, channel=channel).declare()

    return connection, channel, exchange


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="DockingService",
        description="Performs docking using AutoDock Vina"
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
                    [Queue("DockingTask",
                     exchange=Exchange("AsyncAPI.Models:DockingTask", "fanout"))],
                    config)
    worker.run()
