from datetime import datetime
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .models import HandoffItem, HandoffRecord, RiskLevel
from .storage import Storage
from .markdown import render_markdown, save_markdown, render_markdown_grouped, save_markdown_grouped
from .grouper import ShiftGroup, group_by_shift


app = typer.Typer(help="值班交接命令行工具 - 记录交接事项、标记风险、输出 Markdown 摘要")
console = Console()
storage = Storage()


RISK_STYLE = {
    RiskLevel.LOW: "green",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.HIGH: "orange",
    RiskLevel.CRITICAL: "bold red",
}

RISK_ICON = {
    RiskLevel.LOW: "●",
    RiskLevel.MEDIUM: "●",
    RiskLevel.HIGH: "●",
    RiskLevel.CRITICAL: "●",
}


def _print_risk(level: RiskLevel) -> Text:
    return Text(f"{RISK_ICON[level]} {level.value.upper()}", style=RISK_STYLE[level])


def _get_record_or_error(shift_name: str) -> Optional[HandoffRecord]:
    record = storage.get_record(shift_name)
    if not record:
        console.print(f"[bold red]错误[/bold red]: 未找到班次 '{shift_name}'")
        return None
    return record


@app.command("init")
def init_shift(
    shift_name: str = typer.Argument(..., help="班次名称，如 '2026-06-13-day'"),
    operator: str = typer.Option(..., "--operator", "-o", help="值班人姓名"),
    start_time: Optional[str] = typer.Option(None, "--start", "-s", help="开始时间，默认当前时间"),
):
    """初始化一个新的值班班次"""
    if storage.get_record(shift_name):
        console.print(f"[bold yellow]警告[/bold yellow]: 班次 '{shift_name}' 已存在")
        raise typer.Exit(code=1)

    start = start_time or datetime.now().strftime("%Y-%m-%d %H:%M")
    record = HandoffRecord(
        shift_name=shift_name,
        operator=operator,
        start_time=start,
    )
    storage.save_record(record)
    console.print(f"[bold green]✓[/bold green] 已创建班次: {shift_name}")
    console.print(f"  值班人: {operator}")
    console.print(f"  开始时间: {start}")


def _render_risk_badge_set(levels):
    if not levels:
        return "—"
    ordered = [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]
    text = Text()
    first = True
    for lv in ordered:
        if lv in levels:
            if not first:
                text.append(" ")
            text.append(f"{RISK_ICON[lv]} {lv.value.upper()}", style=RISK_STYLE[lv])
            first = False
    return text


@app.command("list")
def list_shifts(
    group_by: Optional[str] = typer.Option(None, "--group-by", help="分组方式：shift（按值班周期）"),
):
    """列出所有值班班次"""
    records = storage.list_records()
    if not records:
        console.print("[yellow]暂无值班记录[/yellow]")
        return

    if group_by == "shift":
        groups = group_by_shift(records)
        for idx, group in enumerate(groups, 1):
            header = Text.assemble(
                Text(f" 值班周期 #{idx} ", style="bold white on magenta"),
                Text(f"  👤 {group.operator}  ", style="bold magenta"),
            )
            meta = Text.assemble(
                Text("⏱  ", style="dim"),
                Text(f"{group.start_time} → {group.end_time}"),
            )
            console.print()
            console.print(Panel.fit(meta, title=header, border_style="magenta"))

            badge_text = _render_risk_badge_set(group.risk_levels)
            info = Table.grid(padding=(0, 4))
            info.add_column(style="dim", width=12)
            info.add_column()
            info.add_row("风险标签:", badge_text)
            info.add_row("包含班次:", ", ".join(r.shift_name for r in group.records))
            info.add_row("事项总数:", str(group.total_items) + (f" (高风险 {group.high_risk_count})" if group.high_risk_count else ""))
            console.print(info)

            table = Table(show_lines=False, header_style="bold")
            table.add_column("班次", style="cyan", no_wrap=True)
            table.add_column("开始时间", style="green")
            table.add_column("结束时间", style="green")
            table.add_column("事项数", justify="right")
            table.add_column("高风险", justify="right", style="red")
            for r in group.records:
                high_risk = sum(1 for i in r.items if i.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL))
                table.add_row(
                    r.shift_name,
                    r.start_time,
                    r.end_time or "-",
                    str(len(r.items)),
                    str(high_risk) if high_risk > 0 else "0",
                )
            console.print(table)
        return

    table = Table(title="值班班次列表", show_lines=False)
    table.add_column("班次", style="cyan", no_wrap=True)
    table.add_column("值班人", style="magenta")
    table.add_column("开始时间", style="green")
    table.add_column("结束时间", style="green")
    table.add_column("事项数", justify="right")
    table.add_column("高风险", justify="right", style="red")

    for r in records:
        high_risk = sum(1 for i in r.items if i.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL))
        table.add_row(
            r.shift_name,
            r.operator,
            r.start_time,
            r.end_time or "-",
            str(len(r.items)),
            str(high_risk) if high_risk > 0 else "0",
        )

    console.print(table)


@app.command("show")
def show_shift(
    shift_name: str = typer.Argument(..., help="班次名称"),
):
    """查看某个班次的详细交接事项"""
    record = _get_record_or_error(shift_name)
    if not record:
        raise typer.Exit(code=1)

    header = f"[bold cyan]{record.shift_name}[/bold cyan]"
    subtitle = f"值班人: {record.operator} | 开始: {record.start_time}"
    if record.end_time:
        subtitle += f" | 结束: {record.end_time}"

    console.print(Panel.fit(subtitle, title=header, border_style="cyan"))

    if record.notes:
        console.print()
        console.print(Panel(record.notes, title="值班备注", border_style="blue"))

    if not record.items:
        console.print()
        console.print("[yellow]暂无交接事项[/yellow]")
        return

    console.print()
    for item in record.items:
        risk_text = _print_risk(item.risk)
        title = Text.assemble(
            Text(f"#{item.id} ", style="bold"),
            Text(item.title, style="bold white"),
        )
        item_panel = Table.grid(padding=(0, 2))
        item_panel.add_column(style="dim", width=8)
        item_panel.add_column()
        item_panel.add_row("风险:", risk_text)
        item_panel.add_row("状态:", item.status)
        if item.owner:
            item_panel.add_row("负责人:", item.owner)
        if item.tags:
            tags_str = ", ".join(f"[{t}]" for t in item.tags)
            item_panel.add_row("标签:", tags_str)
        item_panel.add_row("描述:", item.description)

        console.print(Panel(item_panel, title=title, border_style="dim"))
        console.print()


@app.command("add")
def add_item(
    shift_name: str = typer.Argument(..., help="班次名称"),
    title: str = typer.Argument(..., help="事项标题"),
    description: str = typer.Option("", "--desc", "-d", help="详细描述"),
    risk: RiskLevel = typer.Option(RiskLevel.LOW, "--risk", "-r", help="风险等级"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", "-t", help="标签，可多次指定"),
    owner: str = typer.Option("", "--owner", "-O", help="负责人"),
):
    """向班次添加交接事项"""
    record = _get_record_or_error(shift_name)
    if not record:
        raise typer.Exit(code=1)

    item = HandoffItem(
        id=0,
        title=title,
        description=description,
        risk=risk,
        tags=tags or [],
        owner=owner,
    )
    record = storage.add_item(shift_name, item)
    if not record:
        raise typer.Exit(code=1)

    new_item = record.items[-1]
    console.print(
        f"[bold green]✓[/bold green] 已添加事项 #{new_item.id} "
        f"[{new_item.risk.value.upper()}] {new_item.title}"
    )


@app.command("risk")
def set_risk(
    shift_name: str = typer.Argument(..., help="班次名称"),
    item_id: int = typer.Argument(..., help="事项 ID"),
    risk: RiskLevel = typer.Argument(..., help="风险等级: low/medium/high/critical"),
):
    """设置事项的风险等级"""
    record = storage.update_item_risk(shift_name, item_id, risk)
    if not record:
        console.print(f"[bold red]错误[/bold red]: 未找到班次或事项")
        raise typer.Exit(code=1)
    console.print(
        f"[bold green]✓[/bold green] 事项 #{item_id} 风险等级已更新为 "
        f"[{risk.value.upper()}]"
    )


@app.command("status")
def set_status(
    shift_name: str = typer.Argument(..., help="班次名称"),
    item_id: int = typer.Argument(..., help="事项 ID"),
    status: str = typer.Argument(..., help="状态: pending/in_progress/resolved/blocked"),
):
    """设置事项的处理状态"""
    record = storage.update_item_status(shift_name, item_id, status)
    if not record:
        console.print(f"[bold red]错误[/bold red]: 未找到班次或事项")
        raise typer.Exit(code=1)
    console.print(f"[bold green]✓[/bold green] 事项 #{item_id} 状态已更新为 [{status}]")


@app.command("delete")
def delete_item(
    shift_name: str = typer.Argument(..., help="班次名称"),
    item_id: int = typer.Argument(..., help="事项 ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
):
    """删除班次中的事项"""
    record = _get_record_or_error(shift_name)
    if not record:
        raise typer.Exit(code=1)

    target = next((i for i in record.items if i.id == item_id), None)
    if not target:
        console.print(f"[bold red]错误[/bold red]: 未找到事项 #{item_id}")
        raise typer.Exit(code=1)

    if not confirm:
        typer.confirm(f"确定要删除事项 #{item_id}: {target.title} ?", abort=True)

    storage.delete_item(shift_name, item_id)
    console.print(f"[bold green]✓[/bold green] 已删除事项 #{item_id}")


@app.command("note")
def add_note(
    shift_name: str = typer.Argument(..., help="班次名称"),
    note: str = typer.Argument(..., help="备注内容"),
    append: bool = typer.Option(True, "--append/--overwrite", help="追加或覆盖"),
):
    """添加或更新班次备注"""
    record = _get_record_or_error(shift_name)
    if not record:
        raise typer.Exit(code=1)

    if append and record.notes:
        record.notes = record.notes + "\n" + note
    else:
        record.notes = note

    storage.save_record(record)
    console.print(f"[bold green]✓[/bold green] 已更新备注")


@app.command("summary")
def summary(
    shift_names: Optional[List[str]] = typer.Argument(None, help="班次名称（可多个，省略则结合 --all 使用）"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出文件路径，默认打印到终端"),
    end_time: Optional[str] = typer.Option(None, "--end", "-e", help="值班结束时间（仅单班次有效）"),
    all_shifts: bool = typer.Option(False, "--all", help="导出全部班次"),
    group_by: Optional[str] = typer.Option(None, "--group-by", help="分组方式：shift（按值班周期）"),
    title: str = typer.Option("值班交接汇总", "--title", help="Markdown 标题"),
):
    """生成 Markdown 格式的交接摘要"""
    if shift_names:
        records = []
        for name in shift_names:
            r = storage.get_record(name)
            if not r:
                console.print(f"[bold red]错误[/bold red]: 未找到班次 '{name}'")
                raise typer.Exit(code=1)
            records.append(r)
    elif all_shifts:
        records = storage.list_records()
        if not records:
            console.print("[yellow]暂无值班记录[/yellow]")
            raise typer.Exit(code=1)
    else:
        console.print("[bold red]错误[/bold red]: 请指定班次名称，或使用 --all 导出全部班次")
        raise typer.Exit(code=1)

    if len(records) == 1 and not group_by:
        record = records[0]
        if end_time:
            record.end_time = end_time
            storage.save_record(record)
        elif not record.end_time:
            record.end_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        if output:
            path = save_markdown(record, output)
            console.print(f"[bold green]✓[/bold green] Markdown 摘要已保存到: {path}")
        else:
            console.print(render_markdown(record))
        return

    if group_by == "shift":
        if output:
            path = save_markdown_grouped(records, output, title=title)
            console.print(f"[bold green]✓[/bold green] 按值班周期分组的 Markdown 摘要已保存到: {path}")
        else:
            console.print(render_markdown_grouped(records, title=title))
        return

    if output:
        path = save_markdown_grouped(records, output, title=title)
        console.print(f"[bold green]✓[/bold green] Markdown 摘要已保存到: {path}")
    else:
        console.print(render_markdown_grouped(records, title=title))


def main():
    app()


if __name__ == "__main__":
    main()
