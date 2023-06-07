from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from kombu import Connection, Exchange, Queue, Producer
from kombu.mixins import ConsumerProducerMixin
from time import sleep
from random import uniform
import smtplib
import logging
import yaml
import argparse

def send_mail(msg, config):
    try:
        logging.info("Connecting to SMTP")
        logging.info(config["smtp_server"])
        logging.info(config["smtp_port"])
        if config["ssl"]:
            server = smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"])
        else:
            server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        logging.info("Sending ehlo")
        server.ehlo()
        if (config["smtp_login"] != ""):
            logging.info("Logging in")
            server.login(config["smtp_login"], config["smtp_pw"])
        logging.info("Sending msg")
        server.send_message(msg)
        logging.info("Msg send!")
        server.quit()
    except Exception as e:
        logging.error(e)
        return 1

    return 0

def initialize_logging(mod_name):
    logger = logging.getLogger(mod_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger

class Worker(ConsumerProducerMixin):
    def __init__(self, connection, queues, config):
        self.connection = connection
        self.queues = queues
        self.logger = initialize_logging("MailService")
        self.config = config

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=self.queues, callbacks=[self.on_message])]

    def on_message(self, body, message):
        self.logger.info(f"Received message {body}")
        email = MIMEMultipart("alternative")
        email["Subject"] = body["subject"]
        email["From"] = formataddr(('ReverseDock', "findr@biologie.uni-freiburg.de"))
        email["To"] = body["recipient"]
        email.attach(MIMEText(body["bodyRaw"], "plain"))
        email.attach(MIMEText(body["bodyHTML"], "html"))
        if (send_mail(email, self.config) == 0):
            message.ack()
        else:
            message.reject(requeue=False)
        

def setup_mq(host):
    connection = Connection(host, heartbeat=120)
    channel = connection.channel()

    return connection, channel


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="MailService",
        description="Sends emails"
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

    connection, channel = setup_mq(config["service"]["rabbitmq"])

    worker = Worker(connection,
                    [Queue("MailTask",
                     exchange=Exchange("AsyncAPI.Models:MailTask", "fanout"))],
                    config)
    worker.run()
