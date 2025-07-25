import asyncio
import websockets
import json

clients = {}

async def handle_client(websocket):
    client_id = str(id(websocket))
    clients[client_id] = websocket
    print(f"[+] Client connected: {client_id}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)

                if data.get("type") == "pos":
                    if not all(k in data for k in ('id', 'x', 'y', 'z')):
                        print(f"[!] Invalid position data from {client_id}: {data}")
                        continue

                    payload = {
                        'type': 'pos',
                        'id': data['id'],
                        'name': data.get('name', 'Player'),
                        'x': data['x'],
                        'y': data['y'],
                        'z': data['z'],
                        'color': data.get('color', '#3498db')  # include color
                    }

                    disconnected = []

                    for other_id, other_ws in clients.items():
                        if other_id != client_id:
                            try:
                                await other_ws.send(json.dumps(payload))
                            except Exception as e:
                                print(f"[!] Failed to send to {other_id}: {e}")
                                disconnected.append(other_id)

                    for d in disconnected:
                        if d in clients:
                            del clients[d]
                            print(f"[-] Cleaned up dead client: {d}")

            except json.JSONDecodeError:
                print(f"[!] JSON decode error from {client_id}")
            except Exception as e:
                print(f"[!] Error handling message from {client_id}: {e}")

    except Exception as e:
        print(f"[!] Client {client_id} connection closed with error: {e}")

    finally:
        if client_id in clients:
            del clients[client_id]
            print(f"[-] Client disconnected: {client_id}")

async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("[🌐] Server running on ws://0.0.0.0:8765")
    await server.wait_closed()

asyncio.run(main())
