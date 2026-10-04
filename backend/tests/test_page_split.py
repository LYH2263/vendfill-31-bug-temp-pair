from app.services.page_split import present_full, present_summary, present_ticket


def test_summary_uses_same_numbers_as_ticket():
    # 汇总页与补货单同一口径：补量合计而非缺口合计，计数来自同一份 summarize 结果
    payload = {
        "id": 9,
        "total_fill": 4,
        "need_fill_count": 1,
        "full_count": 1,
        "overbooked_count": 0,
        "conflict_count": 1,
        "pending_slots": ["A1"],
        "lines": [
            {"lane_id": 1, "gap": 7, "fill_qty": 4, "status": "need_fill"},
            {"lane_id": 2, "gap": 0, "fill_qty": 0, "status": "full"},
        ],
    }
    s = present_summary(1, payload)
    assert s["total_fill"] == 4
    assert s["need_fill_count"] == 1
    assert s["full_count"] == 1
    assert s["overbooked_count"] == 0
    assert s["conflict_count"] == 1
    assert s["pending_slots"] == ["A1"]


def test_full_list_keeps_zero_fill_and_blocked_labels():
    payload = {
        "lines": [
            {"lane_id": 1, "fill_qty": 0, "status": "blocked", "reason": "货道封锁"},
            {"lane_id": 2, "fill_qty": 3, "status": "need_fill", "reason": ""},
            {"lane_id": 3, "fill_qty": 0, "status": "overbooked", "reason": "超占"},
        ]
    }
    body = present_full(1, payload)
    ids = {l["lane_id"] for l in body["lanes"]}
    assert ids == {1, 3}


def test_full_list_excludes_conflict_zeroed_lanes():
    # 冷热冲突置 0 道仍有缺口，只是本轮让位，不进满仓名单
    payload = {
        "lines": [
            {"lane_id": 1, "gap": 15, "fill_qty": 15, "status": "need_fill", "reason": ""},
            {"lane_id": 2, "gap": 15, "fill_qty": 0, "status": "need_fill", "reason": "冷热相邻冲突"},
            {"lane_id": 3, "gap": 0, "fill_qty": 0, "status": "full", "reason": ""},
            {"lane_id": 4, "gap": -2, "fill_qty": 0, "status": "overbooked", "reason": ""},
        ]
    }
    body = present_full(1, payload)
    ids = {l["lane_id"] for l in body["lanes"]}
    assert ids == {3, 4}


def test_ticket_keeps_row_fill_qty():
    payload = {"lines": [{"lane_id": 1, "fill_qty": 4, "gap": 9}]}
    t = present_ticket(payload)
    assert t["total_fill"] == 4
