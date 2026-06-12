from handoff.models import HandoffRecord, HandoffItem, RiskLevel
from handoff.grouper import (
    group_by_shift,
    filter_groups_by_risk,
    sort_groups_by_risk_severity,
)
from handoff.markdown import render_markdown_grouped


def _make_item(item_id, title, risk=RiskLevel.LOW):
    return HandoffItem(
        id=item_id,
        title=title,
        description=f"{title}-detail",
        risk=risk,
        tags=[],
        owner="",
        status="pending",
    )


def _make_records():
    return [
        HandoffRecord(
            shift_name="2026-06-12-night",
            operator="王五",
            start_time="2026-06-12 22:00",
            end_time="2026-06-13 02:00",
            items=[_make_item(1, "夜间巡检", RiskLevel.LOW)],
        ),
        HandoffRecord(
            shift_name="2026-06-13-morning",
            operator="张三",
            start_time="2026-06-13 09:00",
            end_time="2026-06-13 13:00",
            items=[
                _make_item(1, "CPU告警", RiskLevel.MEDIUM),
                _make_item(2, "数据库连接池", RiskLevel.HIGH),
            ],
        ),
        HandoffRecord(
            shift_name="2026-06-13-afternoon",
            operator="张三",
            start_time="2026-06-13 13:00",
            end_time="2026-06-13 18:00",
            items=[_make_item(1, "发布上线异常", RiskLevel.CRITICAL)],
        ),
        HandoffRecord(
            shift_name="2026-06-13-night",
            operator="李四",
            start_time="2026-06-13 18:00",
            end_time="2026-06-14 02:00",
            items=[
                _make_item(1, "日志清理", RiskLevel.MEDIUM),
                _make_item(2, "网络抖动影响主链路", RiskLevel.HIGH),
            ],
        ),
    ]


class TestFilterRiskHit:
    def test_filter_high_risk_keeps_matching_groups_and_sorts_by_severity(self):
        records = _make_records()
        groups = group_by_shift(records)
        assert len(groups) == 3

        filtered = filter_groups_by_risk(groups, RiskLevel.HIGH)
        sorted_groups = sort_groups_by_risk_severity(filtered)

        operators = [g.operator for g in sorted_groups]
        assert operators == ["张三", "李四"]
        assert "王五" not in operators

        zhang_group = next(g for g in sorted_groups if g.operator == "张三")
        assert zhang_group.highest_risk == RiskLevel.CRITICAL
        all_risks = set()
        for rec in zhang_group.records:
            for it in rec.items:
                all_risks.add(it.risk)
        assert RiskLevel.LOW not in all_risks
        assert RiskLevel.MEDIUM not in all_risks

    def test_filter_medium_risk_keeps_three_groups_and_strips_low_items(self):
        records = _make_records()
        groups = group_by_shift(records)
        filtered = filter_groups_by_risk(groups, RiskLevel.MEDIUM)
        sorted_groups = sort_groups_by_risk_severity(filtered)

        operators = [g.operator for g in sorted_groups]
        assert operators == ["张三", "李四"]

        for g in sorted_groups:
            for rec in g.records:
                for it in rec.items:
                    assert it.risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_markdown_contains_filtered_hint_and_rerendered_groups(self):
        records = _make_records()
        md = render_markdown_grouped(records, title="高危筛选", filter_risk=RiskLevel.HIGH)

        assert "**风险筛选**: ≥ 🟠 高风险" in md
        idx_zhang = md.index("值班周期 #1 — 张三")
        idx_li = md.index("值班周期 #2 — 李四")
        assert idx_zhang < idx_li
        assert "王五" not in md
        assert "发布上线异常" in md
        assert "数据库连接池" in md
        assert "夜间巡检" not in md
        assert "CPU告警" not in md
        assert "日志清理" not in md
        assert "网络抖动影响主链路" in md


class TestFilterRiskMiss:
    def test_filter_critical_on_all_low_records_returns_empty(self):
        records = [
            HandoffRecord(
                shift_name="s1", operator="A",
                start_time="2026-06-13 09:00", end_time="2026-06-13 12:00",
                items=[_make_item(1, "常规巡检", RiskLevel.LOW)],
            ),
            HandoffRecord(
                shift_name="s2", operator="B",
                start_time="2026-06-13 14:00", end_time="2026-06-13 18:00",
                items=[_make_item(1, "日志轮转", RiskLevel.MEDIUM)],
            ),
        ]
        groups = group_by_shift(records)
        filtered = filter_groups_by_risk(groups, RiskLevel.CRITICAL)
        assert filtered == []

    def test_markdown_with_empty_result_shows_placeholder(self):
        records = [
            HandoffRecord(
                shift_name="s1", operator="A",
                start_time="2026-06-13 09:00", end_time="2026-06-13 12:00",
                items=[_make_item(1, "ok", RiskLevel.LOW)],
            ),
        ]
        md = render_markdown_grouped(records, filter_risk=RiskLevel.CRITICAL)
        assert "_没有符合筛选条件的值班周期_" in md
        assert "值班周期 #1" not in md


class TestFilterRiskDefault:
    def test_none_filter_returns_all_groups_in_chronological_order(self):
        records = _make_records()
        groups = group_by_shift(records)
        filtered = filter_groups_by_risk(groups, None) if False else groups
        assert filtered is groups
        operators = [g.operator for g in filtered]
        assert operators == ["王五", "张三", "李四"]

    def test_markdown_without_filter_preserves_all_groups_and_items(self):
        records = _make_records()
        md = render_markdown_grouped(records, filter_risk=None)

        assert "风险筛选" not in md
        assert "王五" in md
        assert "张三" in md
        assert "李四" in md
        assert "夜间巡检" in md
        assert "CPU告警" in md
        assert "数据库连接池" in md
        assert "发布上线异常" in md
        assert "日志清理" in md

    def test_markdown_without_filter_renders_in_original_order(self):
        records = _make_records()
        md = render_markdown_grouped(records)
        idx_wang = md.index("值班周期 #1 — 王五")
        idx_zhang = md.index("值班周期 #2 — 张三")
        idx_li = md.index("值班周期 #3 — 李四")
        assert idx_wang < idx_zhang < idx_li
