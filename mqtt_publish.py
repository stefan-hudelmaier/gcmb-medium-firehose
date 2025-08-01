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

    def __init__(self, target_rate=1, min_buffer_size=5, max_buffer_size=20):
        """
        Initialize the MQTT Publisher with rate control parameters.

        Args:
            target_rate: Target publishing rate in messages per second
            min_buffer_size: Minimum buffer size to maintain
            max_buffer_size: Maximum buffer size before increasing publish rate
        """
        self.mqtt_client = self._connect_mqtt()
        self.msg_queue = queue.Queue(maxsize=100000)
        self.start_time = time.time()
        self.last_successful_message = None

        # Rate control parameters
        self.target_rate = target_rate  # messages per second
        self.min_buffer_size = min_buffer_size
        self.max_buffer_size = max_buffer_size
        self.current_rate = target_rate
        self.last_rate_adjustment = time.time()
        self.rate_adjustment_interval = 5.0  # seconds between rate adjustments

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


    def _adjust_publishing_rate(self, queue_size):
        """
        Adjusts the publishing rate based on the current buffer size.

        Args:
            queue_size: Current size of the message queue

        Returns:
            float: The new publishing rate in messages per second
        """
        logger.debug(f"Rate control: Adjusting rate - current buffer size={queue_size}, " +
                    f"current_rate={self.current_rate:.2f} msg/s, target_rate={self.target_rate:.2f} msg/s")

        previous_rate = self.current_rate

        # Adjust rate based on buffer size
        if queue_size < self.min_buffer_size:
            # Buffer is too small, decrease rate to prevent emptying
            self.current_rate = max(0.5, self.current_rate * 0.9)
            logger.debug(f"Rate control: Buffer below minimum ({queue_size} < {self.min_buffer_size}), " +
                        f"decreasing rate from {previous_rate:.2f} to {self.current_rate:.2f} msg/s")
        elif queue_size > self.max_buffer_size:
            # Buffer is too large, increase rate to prevent overflow
            self.current_rate = min(self.current_rate * 1.1, 100)  # Cap at 100 msg/s
            logger.debug(f"Rate control: Buffer above maximum ({queue_size} > {self.max_buffer_size}), " +
                        f"increasing rate from {previous_rate:.2f} to {self.current_rate:.2f} msg/s")
        elif queue_size > self.min_buffer_size * 2 and self.current_rate < self.target_rate:
            # Buffer is healthy but rate is below target, gradually increase
            self.current_rate = min(self.current_rate * 1.05, self.target_rate)
            logger.debug(f"Rate control: Buffer healthy ({queue_size} > {self.min_buffer_size * 2}) but rate below target, " +
                        f"increasing from {previous_rate:.2f} to {self.current_rate:.2f} msg/s")
        elif queue_size <= self.min_buffer_size * 2 and self.current_rate > self.target_rate * 0.5:
            # Buffer is close to minimum and rate is above half the target, gradually decrease
            self.current_rate = max(self.current_rate * 0.95, self.target_rate * 0.5)
            logger.debug(f"Rate control: Buffer close to minimum ({queue_size} <= {self.min_buffer_size * 2}), " +
                        f"decreasing rate from {previous_rate:.2f} to {self.current_rate:.2f} msg/s")
        else:
            # No change needed
            logger.debug(f"Rate control: No adjustment needed, maintaining rate at {self.current_rate:.2f} msg/s")

        return self.current_rate

    def _publish_msg_queue_messages(self):
        """
        Publishes messages from the queue at a controlled rate.
        Adjusts the rate based on the buffer size to maintain a constant flow.
        """
        while True:
            try:
                # Calculate the time to wait between messages based on current rate
                wait_time = 1.0 / self.current_rate if self.current_rate > 0 else 0.1

                # Check if we need to adjust the rate based on buffer size
                current_time = time.time()
                if current_time - self.last_rate_adjustment >= self.rate_adjustment_interval:
                    queue_size = self.msg_queue.qsize()

                    # Log current status
                    logger.debug(f"Buffer status: size={queue_size}, current_rate={self.current_rate:.2f} msg/s")

                    # Adjust rate based on buffer size
                    self._adjust_publishing_rate(queue_size)

                    self.last_rate_adjustment = current_time

                # Get message from queue with a timeout to prevent blocking
                try:
                    msg, topic = self.msg_queue.get(timeout=0.1)

                    # Publish the message
                    successful_publish = self._publish(topic, msg)
                    if successful_publish:
                        self.last_successful_message = time.time()

                    # Wait to maintain the desired rate
                    time.sleep(wait_time)

                except queue.Empty:
                    # Queue is empty, wait a bit before checking again
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Exception publishing message", exc_info=True)
                # Wait a bit before retrying to prevent tight error loops
                time.sleep(1.0)


    def send_msg(self, msg, topic):
        """
        Queue a message to be published to the specified topic.

        Args:
            msg: The message content to publish
            topic: The MQTT topic to publish to
        """
        self.msg_queue.put((msg, topic,))
        logger.debug(f"Message queued: {msg}")

    def get_buffer_status(self):
        """
        Get the current status of the message buffer and publishing rate.

        Returns:
            dict: A dictionary containing buffer size, current rate, and target rate
        """
        return {
            "buffer_size": self.msg_queue.qsize(),
            "current_rate": self.current_rate,
            "target_rate": self.target_rate,
            "min_buffer_size": self.min_buffer_size,
            "max_buffer_size": self.max_buffer_size
        }


    def _watchdog(self):
        while True:
            time.sleep(60)
            if self.last_successful_message is not None and time.time() - self.last_successful_message > 10 * 60:
                logger.error("No messages received in the 10 minutes, restarting")
                # sys.exit would not work in a thread
                os._exit(1)
