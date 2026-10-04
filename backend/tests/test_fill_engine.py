from app.services.fill_engine import (
    CONFLICT_REASON,
    build_fill_lines,
    compute_gap,
    is_cold_hot_adjacent,
    summarize,
)


def _lane(id, slot, zone=None, cap=20, stock=5, transit=0, loc=1):
    return {"id": id, "location_id": loc, "slot_no": slot, "sku_name": slot,
            "capacity": cap, "stock": stock, "in_transit": transit, "zone": zone}


def by_slot(lines, slot):
    return next(l for l in lines if l.slot_no == slot)

def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5

def test_no_negative_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 12, "in_transit": 0}]
    lines = build_fill_lines(lanes)
    assert lines[0].fill_qty == 0
    assert lines[0].status == "overbooked"

def test_cap_by_gap():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0}]
    lines = build_fill_lines(lanes, requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15

def test_full_zero_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 8, "in_transit": 2}]
    s = summarize(build_fill_lines(lanes))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0


# ---------- 冷热邻道互斥 ----------

def test_adjacency_predicate():
    assert is_cold_hot_adjacent("cold", "hot")
    assert is_cold_hot_adjacent("hot", "cold")
    # 未标温区按热兼容：冷 vs 未标冲突，热/未标彼此不冲突
    assert is_cold_hot_adjacent("cold", None)
    assert not is_cold_hot_adjacent("hot", None)
    assert not is_cold_hot_adjacent(None, None)
    assert not is_cold_hot_adjacent("cold", "cold")
    assert not is_cold_hot_adjacent("hot", "hot")


def test_seed_a1_cold_a2_hot_later_slot_zero():
    # A1 冷、A2 热，编号相邻且均有缺口：编号靠后的 A2 置 0，A1 按缺口补
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot")]
    lines = build_fill_lines(lanes)
    a1, a2 = by_slot(lines, "A1"), by_slot(lines, "A2")
    assert a1.fill_qty == a1.gap == 15          # 编号靠前道按缺口正常补
    assert a2.fill_qty == 0 and a2.gap == 15     # 编号靠后道强制 0
    assert a2.reason == CONFLICT_REASON
    assert a1.reason == ""
    # 冲突道仍是待补（有缺口），不计入满仓
    assert a2.status == "need_fill"
    s = summarize(lines)
    assert "A2" not in s["pending_slots"]
    assert "A1" in s["pending_slots"]
    assert s["conflict_count"] == 1
    assert s["total_fill"] == 15                 # 不得两边都出正补量


def test_blocked_by_slot_order_regardless_of_id():
    # 编号 A1 在前但后登记（id=10 更大），A2 反而是先登记的小 id：
    # 置 0 的仍必须是编号靠后的 A2，与 id/登记先后无关
    lanes = [_lane(3, "A2", "cold"), _lane(10, "A1", "hot")]
    lines = build_fill_lines(lanes)
    a1 = by_slot(lines, "A1")
    a2 = by_slot(lines, "A2")
    assert a1.fill_qty == 15 and a1.reason == ""
    assert a2.fill_qty == 0 and a2.reason == CONFLICT_REASON


def test_change_zone_recalculates_no_double_positive():
    # 初始同为热：双正补量
    lanes = [_lane(1, "A1", "hot"), _lane(2, "A2", "hot")]
    s0 = summarize(build_fill_lines(lanes))
    assert s0["total_fill"] == 30 and s0["conflict_count"] == 0
    # A1 改冷后重新生成：编号靠后的 A2 置 0，禁止仍按旧温区出双正补量
    lanes[0]["zone"] = "cold"
    lines = build_fill_lines(lanes)
    fills = sorted(l.fill_qty for l in lines)
    assert fills == [0, 15]
    assert summarize(lines)["conflict_count"] == 1
    # A2 也改冷：冲突解除，恢复双正补量
    lanes[1]["zone"] = "cold"
    assert summarize(build_fill_lines(lanes))["conflict_count"] == 0


def test_unzoned_treated_as_hot():
    # A1 冷，A2 未标（按热）→ 冲突，编号靠后的 A2 置 0
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", None)]
    lines = build_fill_lines(lanes)
    assert by_slot(lines, "A2").fill_qty == 0
    assert by_slot(lines, "A2").zone == "hot"


def test_unzoned_pair_not_conflict():
    # 未标道按热：热 vs 未标、未标 vs 未标都不得乱掐
    lanes = [_lane(1, "A1", "hot"), _lane(2, "A2", None), _lane(3, "A3", None)]
    s = summarize(build_fill_lines(lanes))
    assert s["conflict_count"] == 0 and s["total_fill"] == 45


def test_adjacency_only_between_neighbors_by_slot():
    # A1 冷、A2 热(冲突置0)、A3 冷：A1/A3 不相邻不互相影响；
    # A3 与 A2 也冲突，编号靠后的 A3 同样置 0，A1 正常补
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot"), _lane(3, "A3", "cold")]
    lines = build_fill_lines(lanes)
    assert by_slot(lines, "A1").fill_qty == 15
    assert by_slot(lines, "A2").fill_qty == 0
    assert by_slot(lines, "A3").fill_qty == 0


def test_blocked_zero_even_with_large_request():
    # 被掐道即便申请量远超缺口，补量也必须为 0，不许两边都正
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot")]
    lines = build_fill_lines(lanes, requested={1: 100, 2: 100})
    assert by_slot(lines, "A1").fill_qty == 15
    assert by_slot(lines, "A2").fill_qty == 0


def test_reason_is_standalone_sentence():
    # 原因只写冷热相邻冲突，不与封锁/上限等并句
    lanes = [_lane(1, "A1", "cold"), _lane(2, "A2", "hot")]
    a2 = by_slot(build_fill_lines(lanes), "A2")
    assert a2.reason == "冷热相邻冲突"
    assert "封锁" not in a2.reason and "上限" not in a2.reason


def test_full_lane_not_flagged_conflict():
    # 编号靠后道本已满仓（缺口0）：补量为0但不写冲突原因
    lanes = [_lane(1, "A1", "cold"),
             _lane(2, "A2", "hot", cap=10, stock=10, transit=0)]
    a2 = by_slot(build_fill_lines(lanes), "A2")
    assert a2.fill_qty == 0 and a2.status == "full" and a2.reason == ""


def test_different_locations_never_adjacent():
    lanes = [_lane(1, "A1", "cold", loc=1), _lane(2, "A1", "hot", loc=2)]
    s = summarize(build_fill_lines(lanes))
    assert s["conflict_count"] == 0 and s["total_fill"] == 30

