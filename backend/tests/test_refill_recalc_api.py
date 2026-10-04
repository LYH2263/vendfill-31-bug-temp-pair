"""改完温区重新生成必须按新标记重算：走真实持久层，防止吃旧配对。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import refills
from app.api.lanes import LaneUpdate, update_lane
from app.database import Base
from app.models.models import Lane, Location


def _db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Location(id=1, code="VM-01", name="测试点位"))
    db.add_all([
        Lane(id=1, location_id=1, slot_no="A1", sku_name="矿泉水",
             capacity=20, stock=5, in_transit=0, zone="hot"),
        Lane(id=2, location_id=1, slot_no="A2", sku_name="可乐",
             capacity=20, stock=5, in_transit=0, zone="hot"),
    ])
    db.commit()
    return db


def _by_slot(ticket, slot):
    return next(l for l in ticket["lines"] if l["slot_no"] == slot)


def test_rerun_after_zone_change_uses_new_pair_everywhere():
    db = _db()
    # 初始双热：两边都出正补量
    first = refills.run_refill(location_id=1, db=db)
    assert [l["fill_qty"] for l in sorted(first["lines"], key=lambda l: l["slot_no"])] == [15, 15]

    # A1 改冷后重新生成：编号靠后的 A2 必须置 0，不许沿用旧的双热结果
    update_lane(1, LaneUpdate(zone="cold"), db)
    ticket = refills.run_refill(location_id=1, db=db)
    a1, a2 = _by_slot(ticket, "A1"), _by_slot(ticket, "A2")
    assert a1["fill_qty"] == 15 and a1["reason"] == ""
    assert a2["fill_qty"] == 0 and a2["reason"] == "冷热相邻冲突"

    # 满仓名单：两车道都有缺口，不得出现被掐的 A2
    full = refills.full_lanes(location_id=1, db=db)
    assert {l["slot_no"] for l in full["lanes"]} == set()

    # 汇总待补集合只剩 A1，总量只算实际补量
    summary = refills.refill_summary(location_id=1, db=db)
    assert summary["pending_slots"] == ["A1"]
    assert summary["total_fill"] == 15
    assert summary["conflict_count"] == 1

    # A2 也改冷：冲突解除，重新生成恢复双正补量
    update_lane(2, LaneUpdate(zone="cold"), db)
    again = refills.run_refill(location_id=1, db=db)
    assert [l["fill_qty"] for l in sorted(again["lines"], key=lambda l: l["slot_no"])] == [15, 15]
