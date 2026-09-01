"""Time-window decisions shared by timeline download modes."""

from __future__ import annotations


def evaluate_time_window(
    timestamp: int,
    start: int,
    end: int,
    *,
    ordered_by_tweet_time: bool = True,
) -> tuple[bool, bool]:
    """Return ``(should_download, should_continue_paging)`` for a tweet.

    Normal media timelines are newest-first by tweet publication time, so an
    item older than ``start`` means later pages can be skipped. Likes timelines
    are ordered by like activity instead, and must keep paging because a later
    item may contain a newer tweet.
    """
    if start <= timestamp <= end:
        return True, True
    if timestamp < start and ordered_by_tweet_time:
        return False, False
    return False, True
