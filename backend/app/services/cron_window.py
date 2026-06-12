from datetime import datetime


CRON_FIELD_RANGES = (
    (0, 59),
    (0, 23),
    (1, 31),
    (1, 12),
    (0, 7),
)


def validate_cron_expression(expression: str | None) -> str | None:
    normalized = _normalize_expression(expression)
    if normalized is None:
        return None
    _parse_cron_expression(normalized)
    return normalized


def cron_matches_now(expression: str | None, now: datetime | None = None) -> bool:
    normalized = validate_cron_expression(expression)
    if normalized is None:
        return True
    current = now or datetime.now()
    minute_values, hour_values, day_values, month_values, week_values = _parse_cron_expression(normalized)
    cron_weekday = (current.weekday() + 1) % 7
    return (
        current.minute in minute_values
        and current.hour in hour_values
        and current.day in day_values
        and current.month in month_values
        and (cron_weekday in week_values or (cron_weekday == 0 and 7 in week_values))
    )


def _normalize_expression(expression: str | None) -> str | None:
    if expression is None:
        return None
    normalized = " ".join(expression.strip().split())
    return normalized or None


def _parse_cron_expression(expression: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("允许执行 Cron 必须是 5 段表达式：分钟 小时 日 月 星期。")
    return tuple(
        _parse_cron_field(field, min_value, max_value)
        for field, (min_value, max_value) in zip(fields, CRON_FIELD_RANGES, strict=True)
    )


def _parse_cron_field(field: str, min_value: int, max_value: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError("允许执行 Cron 包含空字段。")
        values.update(_parse_cron_part(part, min_value, max_value))
    return values


def _parse_cron_part(part: str, min_value: int, max_value: int) -> set[int]:
    base, step_text = part, None
    if "/" in part:
        base, step_text = part.split("/", 1)
        if not step_text.isdigit() or int(step_text) <= 0:
            raise ValueError("允许执行 Cron 的步长必须是正整数。")
    step = int(step_text) if step_text else 1

    if base == "*":
        start, end = min_value, max_value
    elif "-" in base:
        start_text, end_text = base.split("-", 1)
        if not start_text.isdigit() or not end_text.isdigit():
            raise ValueError("允许执行 Cron 的范围必须是数字。")
        start, end = int(start_text), int(end_text)
    elif base.isdigit():
        start = end = int(base)
    else:
        raise ValueError("允许执行 Cron 仅支持 *、数字、范围、列表和步长。")

    if start < min_value or end > max_value or start > end:
        raise ValueError(
            f"允许执行 Cron 字段取值超出范围 {min_value}-{max_value}。"
        )
    return set(range(start, end + 1, step))
