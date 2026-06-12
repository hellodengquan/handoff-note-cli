from handoff.models import HandoffRecord, HandoffItem, RiskLevel
from handoff.grouper import group_by_shift, sort_records_chronologically
from handoff.markdown import render_markdown, render_markdown_grouped


def _make_item(item_id, title, risk=RiskLevel.LOW, tags=None, owner="", status="pending"):
    return HandoffItem(
        id=item_id,
        title=title,
        description=f"{title}详情",
        risk=risk,
        tags=tags or [],
        owner=owner,
        status=status,
    )


class TestSingleShiftNoGrouping:
    def test_single_record_forms_one_group(self):
        record = HandoffRecord(
            shift_name="2026-06-13-day",
            operator="张三",
            start_time="2026-06-13 09:00",
            end_time="2026-06-13 21:00",
            items=[
                _make_item(1, "磁盘告警", RiskLevel.MEDIUM, tags=["disk", "alert"]),
            ],
            notes="平稳值班",
        )
        groups = group_by_shift([record])
        assert len(groups) == 1
        assert groups[0].operator == "张三"
        assert groups[0].start_time == "2026-06-13 09:00"
        assert groups[0].end_time == "2026-06-13 21:00"
        assert groups[0].total_items == 1
        assert RiskLevel.MEDIUM in groups[0].risk_levels

    def test_single_record_markdown_contains_operator_and_summary(self):
        record = HandoffRecord(
            shift_name="2026-06-13-day",
            operator="张三",
            start_time="2026-06-13 09:00",
            end_time="2026-06-13 21:00",
            items=[
                _make_item(1, "磁盘告警", RiskLevel.MEDIUM, tags=["disk"]),
            ],
            notes="平稳值班",
        )
        md = render_markdown(record)
        assert "值班交接记录：2026-06-13-day" in md
        assert "张三" in md
        assert "磁盘告警" in md
        assert "中风险" in md
        groups = group_by_shift([record])
        assert len(groups) == 1


class TestOperatorChangeGrouping:
    def test_three_shifts_with_two_operator_switches_generates_three_groups(self):
        records = [
            HandoffRecord(
                shift_name="2026-06-13-morning",
                operator="张三",
                start_time="2026-06-13 09:00",
                end_time="2026-06-13 13:00",
                items=[_make_item(1, "CPU异常", RiskLevel.LOW)],
            ),
            HandoffRecord(
                shift_name="2026-06-13-afternoon",
                operator="张三",
                start_time="2026-06-13 13:00",
                end_time="2026-06-13 18:00",
                items=[_make_item(1, "内存告警", RiskLevel.HIGH)],
            ),
            HandoffRecord(
                shift_name="2026-06-13-night",
                operator="李四",
                start_time="2026-06-13 18:00",
                end_time="2026-06-13 23:59",
                items=[_make_item(1, "数据库连接池", RiskLevel.CRITICAL)],
            ),
        ]
        groups = group_by_shift(records)
        assert len(groups) == 2

        assert groups[0].operator == "张三"
        assert [r.shift_name for r in groups[0].records] == [
            "2026-06-13-morning",
            "2026-06-13-afternoon",
        ]
        assert groups[0].total_items == 2
        assert RiskLevel.HIGH in groups[0].risk_levels
        assert RiskLevel.LOW in groups[0].risk_levels

        assert groups[1].operator == "李四"
        assert [r.shift_name for r in groups[1].records] == ["2026-06-13-night"]
        assert groups[1].total_items == 1
        assert RiskLevel.CRITICAL in groups[1].risk_levels

    def test_grouped_markdown_contains_each_operator_section(self):
        records = [
            HandoffRecord(
                shift_name="2026-06-13-a",
                operator="张三",
                start_time="2026-06-13 09:00",
                end_time="2026-06-13 15:00",
                items=[_make_item(1, "日志清理", RiskLevel.LOW)],
            ),
            HandoffRecord(
                shift_name="2026-06-13-b",
                operator="李四",
                start_time="2026-06-13 15:00",
                end_time="2026-06-13 21:00",
                items=[_make_item(1, "网络抖动", RiskLevel.MEDIUM)],
            ),
        ]
        md = render_markdown_grouped(records, title="测试交接汇总")
        assert "测试交接汇总" in md
        assert "值班周期 #1" in md
        assert "值班周期 #2" in md
        assert md.index("张三") < md.index("李四")
        assert "日志清理" in md
        assert "网络抖动" in md


class TestCrossDayBoundary:
    def test_same_operator_but_cross_day_splits_group(self):
        records = [
            HandoffRecord(
                shift_name="2026-06-13-night",
                operator="王五",
                start_time="2026-06-13 22:00",
                end_time="2026-06-14 02:00",
                items=[_make_item(1, "夜间巡检", RiskLevel.LOW)],
            ),
            HandoffRecord(
                shift_name="2026-06-14-morning",
                operator="王五",
                start_time="2026-06-14 08:00",
                end_time="2026-06-14 12:00",
                items=[_make_item(1, "发布上线", RiskLevel.HIGH)],
            ),
            HandoffRecord(
                shift_name="2026-06-14-afternoon",
                operator="王五",
                start_time="2026-06-14 13:00",
                end_time="2026-06-14 18:00",
                items=[_make_item(1, "发布后观察", RiskLevel.MEDIUM)],
            ),
        ]
        groups = group_by_shift(records)
        assert len(groups) == 2

        assert groups[0].operator == "王五"
        assert [r.shift_name for r in groups[0].records] == ["2026-06-13-night"]
        assert groups[0].start_time == "2026-06-13 22:00"

        assert groups[1].operator == "王五"
        assert [r.shift_name for r in groups[1].records] == [
            "2026-06-14-morning",
            "2026-06-14-afternoon",
        ]
        assert groups[1].start_time == "2026-06-14 08:00"
        assert groups[1].end_time == "2026-06-14 18:00"

    def test_out_of_order_records_are_sorted_then_grouped(self):
        r1 = HandoffRecord(
            shift_name="shift-c", operator="A",
            start_time="2026-06-14 10:00", end_time="2026-06-14 12:00",
            items=[],
        )
        r2 = HandoffRecord(
            shift_name="shift-a", operator="B",
            start_time="2026-06-12 10:00", end_time="2026-06-12 12:00",
            items=[],
        )
        r3 = HandoffRecord(
            shift_name="shift-b", operator="A",
            start_time="2026-06-13 10:00", end_time="2026-06-13 12:00",
            items=[],
        )
        ordered = sort_records_chronologically([r1, r2, r3])
        assert [r.shift_name for r in ordered] == ["shift-a", "shift-b", "shift-c"]

        groups = group_by_shift([r1, r2, r3])
        assert len(groups) == 3
        assert groups[0].operator == "B"
        assert groups[1].operator == "A"
        assert groups[2].operator == "A"
        assert groups[1].start_time == "2026-06-13 10:00"
        assert groups[2].start_time == "2026-06-14 10:00"

    def test_grouped_markdown_shows_cross_day_split(self):
        records = [
            HandoffRecord(
                shift_name="2026-06-13-night",
                operator="王五",
                start_time="2026-06-13 22:00",
                end_time="2026-06-14 02:00",
                items=[_make_item(1, "夜间巡检", RiskLevel.LOW)],
            ),
            HandoffRecord(
                shift_name="2026-06-14-morning",
                operator="王五",
                start_time="2026-06-14 08:00",
                end_time="2026-06-14 12:00",
                items=[_make_item(1, "发布上线", RiskLevel.HIGH)],
            ),
        ]
        md = render_markdown_grouped(records)
        assert "值班周期 #1" in md
        assert "值班周期 #2" in md
        assert "2026-06-13 22:00" in md
        assert "2026-06-14 08:00" in md
