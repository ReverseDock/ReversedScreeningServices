from kombu import Connection, Exchange, Queue, Producer
from kombu.mixins import ConsumerProducerMixin
import json
from time import sleep
from random import uniform
from DockingPrepper import DockingPrepper, DockingPrepperException
import shutil
import os
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

def createResultMessage(id: str, fullPath: str, fullConfigPath: str):
    message = {
       "message": {
            "id": id,
            "path": fullPath,
            "configPath": fullConfigPath
        },
        "messageType": [
            "urn:message:AsyncAPI.Models:DockingPrepResult"
        ]
    }
    return message

class Worker(ConsumerProducerMixin):
    def __init__(self, connection, queues, config):
        self.connection = connection
        self.queues = queues
        self.logger = initialize_logging("DockingPrepperService")
        self.config = config

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=self.queues, callbacks=[self.on_message], prefetch_count=1)]

    def on_message(self, body, message):
        self.logger.info(f"Received message {body}")
        prepper = DockingPrepper(self.config)
        receptor = body["type"] == 0
        os.makedirs("./" + body["id"], exist_ok=True)
        os.chdir("./" + body["id"])
        copiedFile = shutil.copy(body["path"], "./")
        self.logger.debug(f"Copied '{body['path']}' to '{copiedFile}'")
        try:
            if receptor:
                resultPath = prepper.preparePDBQTReceptor(copiedFile)
            else:
                resultPath = prepper.preparePDBQTLigand(copiedFile)
        except DockingPrepperException:
            message.reject(requeue=False)
            self.logger.info(f"Removing file {copiedFile}")
            os.remove(copiedFile)
            result = createResultMessage(body["id"], None, None)
            self.producer.publish(
                json.dumps(result), exchange="AsyncAPI.Models:DockingPrepResult", retry=True
            )
            os.chdir("../")
            return
        try:
            self.logger.debug(f"Trying to move result from '{resultPath}' to '{body['path'] + 'qt'}'")
            movedResultFile = shutil.move(resultPath, body["path"] + "qt")
        except Exception as e:
            self.logger.error(f"Failed to move result: {e}")
            message.reject(requeue=False)
            result = createResultMessage(body["id"], None, None)
            self.producer.publish(
                json.dumps(result), exchange="AsyncAPI.Models:DockingPrepResult", retry=True
            )
            os.chdir("../")
            return
        self.logger.debug(f"Moved result from '{resultPath}' to '{body['path'] + 'qt'}'")
        os.remove(copiedFile)
        self.logger.debug(f"Removed {copiedFile}")
        configPath = None
        if (receptor):
            try:
                configPath = prepper.prepareConfig(movedResultFile)
            except Exception:
                result = createResultMessage(body["id"], None, None)
                message.reject(requeue=False)
                self.producer.publish(
                    json.dumps(result), exchange="AsyncAPI.Models:DockingPrepResult", retry=True
                )
                return
        result = createResultMessage(body["id"], movedResultFile, configPath)
        self.logger.info(f"Publishing result for message {body}")
        self.producer.publish(
            json.dumps(result), exchange="AsyncAPI.Models:DockingPrepResult", retry=True
        )
        os.chdir("../")
        os.rmdir(body["id"])
        message.ack()

def setup_mq(host):
    connection = Connection(host, heartbeat=0)
    channel = connection.channel()
    exchange = Exchange("AsyncAPI.Models:DockingPrepResult", "fanout", channel=channel)
    exchange.declare()

    Queue("DockingPrepResult", exchange=exchange, channel=channel).declare()

    return connection, channel, exchange


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="DockingPrepperService",
        description="Prepares receptors and ligands for input to AutoDock Vina"
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
                    [Queue("DockingPrepTask",
                     exchange=Exchange("AsyncAPI.Models:DockingPrepTask", "fanout"))],
                    config)
    worker.run()
