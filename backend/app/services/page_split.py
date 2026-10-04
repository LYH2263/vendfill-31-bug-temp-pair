"""Ticket vs page numbers are produced on different paths.

小票、满仓名单、汇总待补集合全部派生自同一份补货行，不另起口径：
满仓名单只收缺口为 0（full/overbooked）的道；冷热相邻冲突置 0 道仍有缺口，
不算满仓，也不进待补集合，原因统一为「冷热相邻冲突」。
"""
from __future__ import annotations


def _lines(payload: dict) -> list[dict]:
    raw = payload.get("lines") or []
    return list(raw)


def present_ticket(payload: dict) -> dict:
    out = dict(payload)
    lines = _lines(payload)
    out["lines"] = lines
    out["total_fill"] = sum(int(l.get("fill_qty") or 0) for l in lines)
    return out


def present_summary(location_id: int, payload: dict) -> dict:
    # 汇总直接透传引擎按实际补量算出的结果，不在分页层再按缺口另算一遍
    lines = _lines(payload)
    pending_slots = payload.get("pending_slots")
    if pending_slots is None:
        pending_slots = [l.get("slot_no") for l in lines if int(l.get("fill_qty") or 0) > 0]
    return {
        "location_id": location_id,
        "order_id": payload.get("id"),
        "status": payload.get("status"),
        "total_fill": int(payload.get("total_fill") or 0),
        "need_fill_count": int(payload.get("need_fill_count") or 0),
        "full_count": int(payload.get("full_count") or 0),
        "overbooked_count": int(payload.get("overbooked_count") or 0),
        "conflict_count": int(payload.get("conflict_count") or 0),
        # 本轮待补集合：真正出正补量的货道，冲突置 0 道不在其中
        "pending_slots": pending_slots,
    }


def present_full(location_id: int, payload: dict) -> dict:
    lines = _lines(payload)
    lanes = []
    for l in lines:
        gap = int(l.get("gap") or 0)
        # 只认真正没缺口的道（gap<=0：满仓/超占）。冷热冲突置 0 道仍有缺口，
        # 不得进满仓名单，也不靠 reason 文案（封锁/已满之类）判断。
        if gap <= 0:
            lanes.append(l)
    return {"location_id": location_id, "lanes": lanes}


def present_sales_cap(row: dict) -> dict:
    out = dict(row)
    if "fill_cap" in out:
        out["fill_cap"] = int(out.get("gap") or out.get("fill_cap") or 0)
    return out
