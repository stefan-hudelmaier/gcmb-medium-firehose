import logging
import os
import queue
import time
from threading import Thread

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger()

broker = 'gcmb.io'
port = 8883
client_id = os.environ.get('MQTT_CLIENT_ID', 'medium/medium-firehose/data-generator/pub')
username = os.environ['MQTT_USERNAME']
password = os.environ['MQTT_PASSWORD']


class MqttPublisher:

    def __init__(self):

        self.mqtt_client = self._connect_mqtt()
        self.msg_queue = queue.Queue(maxsize=100000)
        self.start_time = time.time()
        self.last_successful_message = None

        mqtt_publish_locations_thread = Thread(target=self._publish_msg_queue_messages, args=())
        mqtt_publish_locations_thread.start()

        #watchdog_thread = Thread(target=self._watchdog, args=())
        #watchdog_thread.start()

        mqtt_client_thread = Thread(target=self._mqtt_client_thread, args=())
        mqtt_client_thread.start()


    def _mqtt_client_thread(self):
        self.mqtt_client.loop_forever()

    @staticmethod
    def _connect_mqtt():
        def on_connect(client, userdata, flags, rc, properties):
            if rc == 0:
                logger.info("Connected to MQTT Broker")
            else:
                logger.error(f"Failed to connect, return code {rc}")

        mqtt_client = mqtt.Client(client_id=client_id,
                                  callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.tls_set(ca_certs='/etc/ssl/certs/ca-certificates.crt')
        mqtt_client.username_pw_set(username, password)
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = lambda client, userdata, disconnect_flags, reason_code, properties: logger.warning(
            f"Disconnected from MQTT Broker, return code {reason_code}")
        mqtt_client.connect(broker, port)
        return mqtt_client


    def _publish(self, topic, msg):
        result = self.mqtt_client.publish(topic, msg, retain=False)
        status = result.rc
        if status == 0:
            logger.debug(f"Sent '{msg}' to topic {topic} with id {result.mid}. is_published: {result.is_published()}")
            return True
        else:
            logger.debug(f"Failed to send message to topic {topic}, reason: {status}")
            return False


    def _publish_msg_queue_messages(self):
        while True:
            try:
                msg, topic = self.msg_queue.get()

                successful_publish = self._publish(topic, msg)
                if successful_publish:
                    self.last_successful_message = time.time()

            except Exception as e:
                logger.error(f"Exception publishing message", exc_info=True)


    def send_msg(self, msg, topic):
        self.msg_queue.put((msg, topic,))
        logger.debug(f"Message queued: {msg}")


    def _watchdog(self):
        while True:
            time.sleep(60)
            if self.last_successful_message is not None and time.time() - self.last_successful_message > 10 * 60:
                logger.error("No messages received in the 10 minutes, restarting")
                # sys.exit would not work in a thread
                os._exit(1)
