from typing import List, Optional

from .models import HandoffRecord, RiskLevel
from .grouper import (
    ShiftGroup,
    group_by_shift,
    filter_groups_by_risk,
    sort_groups_by_risk_severity,
)


RISK_EMOJI = {
    RiskLevel.LOW: "🟢",
    RiskLevel.MEDIUM: "🟡",
    RiskLevel.HIGH: "🟠",
    RiskLevel.CRITICAL: "🔴",
}

RISK_LABEL = {
    RiskLevel.LOW: "低风险",
    RiskLevel.MEDIUM: "中风险",
    RiskLevel.HIGH: "高风险",
    RiskLevel.CRITICAL: "严重风险",
}

STATUS_EMOJI = {
    "pending": "⏳",
    "in_progress": "🔧",
    "resolved": "✅",
    "blocked": "🚫",
}


def _render_risk_tag_set(levels) -> str:
    if not levels:
        return "无"
    ordered = [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]
    parts = []
    for lv in ordered:
        if lv in levels:
            parts.append(f"{RISK_EMOJI[lv]} {RISK_LABEL[lv]}")
    return ", ".join(parts)


def _render_single_section(record: HandoffRecord) -> List[str]:
    lines = []

    lines.append(f"### 班次：{record.shift_name}")
    lines.append("")
    lines.append(f"- **开始时间**: {record.start_time}")
    if record.end_time:
        lines.append(f"- **结束时间**: {record.end_time}")

    if record.notes:
        lines.append("")
        lines.append(f"> {record.notes}")
    lines.append("")

    total = len(record.items)
    risk_counts = {level: 0 for level in RiskLevel}
    for item in record.items:
        risk_counts[item.risk] += 1

    if total == 0:
        lines.append("_无交接事项_")
        lines.append("")
        return lines

    lines.append(f"共 {total} 项：")
    for item in record.items:
        tag_risk = f"{RISK_EMOJI[item.risk]} {RISK_LABEL[item.risk]}"
        tag_status = f"{STATUS_EMOJI.get(item.status, '❓')} {item.status}"
        tag_owner = f" 👤 {item.owner}" if item.owner else ""
        tag_tags = "".join(f"`{t}`" for t in item.tags)
        tag_parts = [tag_risk, tag_status]
        if tag_owner:
            tag_parts.append(tag_owner.strip())
        if tag_tags:
            tag_parts.append(tag_tags)
        meta = " · ".join(tag_parts)
        lines.append(f"- **#{item.id} {item.title}** — {meta}")
        if item.description:
            lines.append(f"  - {item.description}")

    lines.append("")
    return lines


def render_markdown(record: HandoffRecord) -> str:
    lines = []

    lines.append(f"# 值班交接记录：{record.shift_name}")
    lines.append("")
    lines.append(f"- **值班人**: {record.operator}")
    lines.append(f"- **开始时间**: {record.start_time}")
    if record.end_time:
        lines.append(f"- **结束时间**: {record.end_time}")
    lines.append(f"- **创建时间**: {record.created_at}")
    lines.append("")

    if record.notes:
        lines.append("## 值班备注")
        lines.append("")
        lines.append(record.notes)
        lines.append("")

    total = len(record.items)
    risk_counts = {level: 0 for level in RiskLevel}
    for item in record.items:
        risk_counts[item.risk] += 1

    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 总事项数: **{total}**")
    for level in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]:
        if risk_counts[level] > 0:
            lines.append(f"- {RISK_EMOJI[level]} {RISK_LABEL[level]}: **{risk_counts[level]}**")
    lines.append("")

    high_risk_items = [i for i in record.items if i.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)]
    if high_risk_items:
        lines.append("## ⚠️ 高风险事项（需重点关注）")
        lines.append("")
        for item in high_risk_items:
            lines.append(f"### {RISK_EMOJI[item.risk]} #{item.id} {item.title}")
            lines.append("")
            lines.append(f"- **风险等级**: {RISK_LABEL[item.risk]}")
            lines.append(f"- **状态**: {STATUS_EMOJI.get(item.status, '❓')} {item.status}")
            if item.owner:
                lines.append(f"- **负责人**: {item.owner}")
            if item.tags:
                lines.append(f"- **标签**: {', '.join(f'`{t}`' for t in item.tags)}")
            lines.append("")
            lines.append(f"**描述**: {item.description}")
            lines.append("")

    other_items = [i for i in record.items if i.risk in (RiskLevel.LOW, RiskLevel.MEDIUM)]
    if other_items:
        lines.append("## 其他事项")
        lines.append("")
        lines.append("| # | 标题 | 风险 | 状态 | 负责人 | 标签 |")
        lines.append("|---|------|------|------|--------|------|")
        for item in other_items:
            tags = ", ".join(item.tags) if item.tags else "-"
            lines.append(
                f"| {item.id} | {item.title} | {RISK_EMOJI[item.risk]} {RISK_LABEL[item.risk]} | "
                f"{STATUS_EMOJI.get(item.status, '❓')} {item.status} | {item.owner or '-'} | {tags} |"
            )
        lines.append("")

    lines.append("---")
    lines.append(f"*由 handoff CLI 自动生成于 {record.created_at}*")

    return "\n".join(lines)


def render_markdown_grouped(
    records: List[HandoffRecord],
    title: str = "值班交接汇总",
    filter_risk: Optional[RiskLevel] = None,
) -> str:
    if not records:
        return f"# {title}\n\n_暂无记录_\n"

    groups = group_by_shift(records)

    if filter_risk is not None:
        groups = filter_groups_by_risk(groups, filter_risk)
        groups = sort_groups_by_risk_severity(groups)

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    if filter_risk is not None:
        lines.append(f"- **风险筛选**: ≥ {RISK_EMOJI[filter_risk]} {RISK_LABEL[filter_risk]}")
    lines.append(f"- 值班周期分组数：**{len(groups)}**")
    lines.append(f"- 总班次：**{len(records)}**")
    lines.append("")

    if not groups:
        lines.append("_没有符合筛选条件的值班周期_")
        lines.append("")
        lines.append("---")
        from datetime import datetime
        lines.append(f"*由 handoff CLI 自动生成于 {datetime.now().isoformat()}*")
        return "\n".join(lines)

    for idx, group in enumerate(groups, 1):
        lines.append("---")
        lines.append("")
        lines.append(f"## 值班周期 #{idx} — {group.operator}")
        lines.append("")
        lines.append(f"- **值班人**: {group.operator}")
        lines.append(f"- **时间范围**: {group.start_time} → {group.end_time}")
        lines.append(f"- **包含班次**: {', '.join(r.shift_name for r in group.records)}")
        lines.append(f"- **风险标签集合**: {_render_risk_tag_set(group.risk_levels)}")
        lines.append(f"- **事项总数**: {group.total_items}" + (f"（高风险 {group.high_risk_count}）" if group.high_risk_count else ""))
        lines.append("")

        for record in group.records:
            lines.extend(_render_single_section(record))

    lines.append("---")
    from datetime import datetime
    lines.append(f"*由 handoff CLI 自动生成于 {datetime.now().isoformat()}*")

    return "\n".join(lines)


def save_markdown(record: HandoffRecord, output_path: Optional[str] = None) -> str:
    content = render_markdown(record)
    if output_path:
        path = output_path
    else:
        path = f"{record.shift_name}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def save_markdown_grouped(
    records: List[HandoffRecord],
    output_path: str,
    title: str = "值班交接汇总",
    filter_risk: Optional[RiskLevel] = None,
) -> str:
    content = render_markdown_grouped(records, title=title, filter_risk=filter_risk)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path
