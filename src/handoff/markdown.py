from typing import Optional

from .models import HandoffRecord, RiskLevel


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


def save_markdown(record: HandoffRecord, output_path: Optional[str] = None) -> str:
    content = render_markdown(record)
    if output_path:
        path = output_path
    else:
        path = f"{record.shift_name}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
