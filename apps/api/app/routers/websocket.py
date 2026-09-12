from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..deps import get_ws_connection_manager, get_ws_facilities, get_ws_routable_graph
from ..routing.graph_builder import RoutableGraph
from ..services.connection_manager import ConnectionManager

router = APIRouter()


def _snapshot(rg: RoutableGraph, facilities: list[dict]) -> dict:
    seen_edge_ids: set[int] = set()
    blocked_edges = []
    for u, v, data in rg.graph.edges(data=True):
        if data["edge_id"] in seen_edge_ids:
            continue
        seen_edge_ids.add(data["edge_id"])
        if data["blocked"]:
            blocked_edges.append({"id": data["edge_id"], "reason": data.get("blocked_reason")})

    return {
        "type": "snapshot",
        "simulated": True,
        "facilities": [
            {"id": f["id"], "type": f["type"], "power_status": f["power_status"]}
            for f in facilities
        ],
        "blocked_edges": blocked_edges,
    }


@router.websocket("/ws/outages")
async def outages_ws(
    websocket: WebSocket,
    connections: ConnectionManager = Depends(get_ws_connection_manager),
    rg: RoutableGraph = Depends(get_ws_routable_graph),
    facilities: list[dict] = Depends(get_ws_facilities),
):
    await connections.connect(websocket)
    try:
        await connections.send_personal(websocket, _snapshot(rg, facilities))
        while True:
            # Keepalive: client is expected to send periodic pings; any inbound
            # message (including a ping) just proves the socket is alive. This
            # also keeps idle proxies (Railway/Render) from dropping the
            # connection during quiet outage-tick intervals.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connections.disconnect(websocket)
