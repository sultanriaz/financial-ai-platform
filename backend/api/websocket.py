class ConnectionManager:
    def __init__(self): self.connections = set()
    async def connect(self, websocket): await websocket.accept(); self.connections.add(websocket)
    def disconnect(self, websocket): self.connections.discard(websocket)
    async def broadcast(self, payload):
        dead = []
        for websocket in self.connections:
            try: await websocket.send_json(payload)
            except Exception: dead.append(websocket)
        for websocket in dead: self.disconnect(websocket)
manager = ConnectionManager()
