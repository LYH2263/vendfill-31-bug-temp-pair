from app.services.page_split import present_full, present_summary, present_ticket


def test_summary_passthrough_engine_fill_totals():
    # 汇总透传引擎按实际补量算出的口径，不再按缺口另加：
    # A1 补4（缺口7），A2 冷热冲突置0（缺口5）→ total_fill 只认 4
    payload = {
        "id": 9,
        "total_fill": 4,
        "need_fill_count": 2,
        "full_count": 0,
        "overbooked_count": 0,
        "conflict_count": 1,
        "pending_slots": ["A1"],
        "lines": [
            {"lane_id": 1, "slot_no": "A1", "gap": 7, "fill_qty": 4, "status": "need_fill", "reason": ""},
            {"lane_id": 2, "slot_no": "A2", "gap": 5, "fill_qty": 0, "status": "need_fill",
             "reason": "冷热相邻冲突"},
        ],
    }
    s = present_summary(1, payload)
    assert s["total_fill"] == 4
    assert s["need_fill_count"] == 2
    assert s["full_count"] == 0
    assert s["conflict_count"] == 1
    assert s["pending_slots"] == ["A1"]


def test_full_list_excludes_conflict_zero_fill_with_gap():
    # 冲突置0道（仍有缺口）不得进满仓名单；只有缺口<=0 的满仓/超占道才进
    payload = {
        "lines": [
            {"lane_id": 1, "slot_no": "A1", "gap": 9, "fill_qty": 0, "status": "need_fill",
             "reason": "冷热相邻冲突"},
            {"lane_id": 2, "slot_no": "A2", "gap": 9, "fill_qty": 3, "status": "need_fill", "reason": ""},
            {"lane_id": 3, "slot_no": "A3", "gap": 0, "fill_qty": 0, "status": "full", "reason": ""},
            {"lane_id": 4, "slot_no": "A4", "gap": -2, "fill_qty": 0, "status": "overbooked", "reason": ""},
        ]
    }
    body = present_full(1, payload)
    ids = {l["lane_id"] for l in body["lanes"]}
    assert ids == {3, 4}


def test_ticket_keeps_row_fill_qty():
    payload = {"lines": [{"lane_id": 1, "fill_qty": 4, "gap": 9}]}
    t = present_ticket(payload)
    assert t["total_fill"] == 4
