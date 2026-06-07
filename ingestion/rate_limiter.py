"""
מגביל קצב בקשות - מגן מפני חריגה ממכסת מסלול ה-Free
(10 בקשות לדקה, 100 ביום). חוסם/ממתין במקום ליפול על שגיאת 429.
"""
from __future__ import annotations

import time
from collections import deque

import config


class RateLimiter:
    def __init__(
        self,
        per_minute: int = config.RATE_LIMIT_PER_MINUTE,
        per_day: int = config.RATE_LIMIT_PER_DAY,
    ):
        self.per_minute = per_minute
        self.per_day = per_day
        self._minute_window: deque[float] = deque()   # חותמות זמן ב-60 שניות האחרונות
        self._day_count = 0
        self._day_start = time.time()

    def _prune_minute(self, now: float) -> None:
        while self._minute_window and now - self._minute_window[0] > 60:
            self._minute_window.popleft()

    def _maybe_reset_day(self, now: float) -> None:
        if now - self._day_start > 86400:
            self._day_count = 0
            self._day_start = now

    def acquire(self) -> None:
        """ממתין במידת הצורך כדי לא לחרוג מהמגבלות. חוסם עד שמותר לשלוח."""
        now = time.time()
        self._maybe_reset_day(now)

        if self._day_count >= self.per_day:
            raise RuntimeError(
                f"הגעת למכסת היום ({self.per_day} בקשות). נסה שוב מחר או שדרג מסלול."
            )

        self._prune_minute(now)
        if len(self._minute_window) >= self.per_minute:
            # להמתין עד שהבקשה הישנה ביותר תצא מחלון הדקה
            sleep_for = 60 - (now - self._minute_window[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.time()
            self._prune_minute(now)

        self._minute_window.append(now)
        self._day_count += 1

    @property
    def remaining_today(self) -> int:
        return max(0, self.per_day - self._day_count)
