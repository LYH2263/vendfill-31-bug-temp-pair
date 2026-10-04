"""小票、满仓、汇总页面共用同一份 build_fill_lines/summarize 结果，口径一致。"""
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
    """汇总页直接采用 summarize() 的口径：与补货单同一份结果，不另算一套。"""
    return {
        "location_id": location_id,
        "order_id": payload.get("id"),
        "total_fill": int(payload.get("total_fill") or 0),
        "need_fill_count": int(payload.get("need_fill_count") or 0),
        "full_count": int(payload.get("full_count") or 0),
        "overbooked_count": int(payload.get("overbooked_count") or 0),
        "conflict_count": int(payload.get("conflict_count") or 0),
        "pending_slots": list(payload.get("pending_slots") or []),
    }


def present_full(location_id: int, payload: dict) -> dict:
    """满仓 = 本轮补量为 0 且缺口 <= 0 的货道。

    冷热冲突置 0 道仍有缺口（gap > 0），只是本轮让位，不属于满仓。
    """
    lanes = []
    for l in _lines(payload):
        fill = int(l.get("fill_qty") or 0)
        gap = int(l.get("gap") or 0)
        if fill == 0 and gap <= 0:
            lanes.append(l)
    return {"location_id": location_id, "lanes": lanes}


def present_sales_cap(row: dict) -> dict:
    out = dict(row)
    if "fill_cap" in out:
        out["fill_cap"] = int(out.get("gap") or out.get("fill_cap") or 0)
    return out
