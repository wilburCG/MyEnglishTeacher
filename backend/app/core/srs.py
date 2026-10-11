"""简化 SM-2 间隔重复算法（纯函数，便于测试）。

grade: 0=不认识(again) 1=模糊(hard) 2=认识(good) 3=很熟(easy)
返回新的 (reps, interval_days, ease_factor, lapses)。
"""
from dataclasses import dataclass

MIN_EASE = 1.3
AGAIN_MINUTES = 10


@dataclass
class SrsState:
    reps: int = 0
    interval_days: int = 0
    ease_factor: float = 2.5
    lapses: int = 0


def grade_quality(grade: int) -> float:
    # SM-2 标准 q 映射：0->2(完全忘记) 1->3 2->4 3->5
    return {0: 2.0, 1: 3.0, 2: 4.0, 3: 5.0}[grade]


def schedule(state: SrsState, grade: int) -> SrsState:
    if grade not in (0, 1, 2, 3):
        raise ValueError("grade must be 0..3")

    q = grade_quality(grade)
    ease = max(
        MIN_EASE,
        state.ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)),
    )

    if grade == 0:
        return SrsState(
            reps=0,
            interval_days=0,
            ease_factor=ease,
            lapses=state.lapses + 1,
        )

    reps = state.reps + 1
    if reps == 1:
        interval = 1 if grade < 3 else 2
    elif reps == 2:
        interval = 3 if grade < 3 else 4
    else:
        interval = max(1, round(state.interval_days * ease))
    return SrsState(
        reps=reps, interval_days=interval, ease_factor=round(ease, 4),
        lapses=state.lapses,
    )


def due_for(interval_days: int, now) -> "datetime":  # noqa: F821
    from datetime import timedelta

    if interval_days == 0:
        return now + timedelta(minutes=AGAIN_MINUTES)
    return now + timedelta(days=interval_days)
