import json
from aiokafka import AIOKafkaProducer

class NewsProducer:
    def __init__(self, bootstrap_servers: str, topic: str):
        self.topic = topic
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            compression_type="gzip",
            linger_ms=20,
        )
    async def start(self): await self.producer.start()
    async def stop(self): await self.producer.stop()
    async def send(self, payload): await self.producer.send_and_wait(self.topic, payload)
