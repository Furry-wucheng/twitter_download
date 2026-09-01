from timeline_utils import evaluate_time_window


def test_normal_timeline_stops_after_reaching_items_older_than_start():
    should_download, should_continue = evaluate_time_window(99, 100, 200)

    assert should_download is False
    assert should_continue is False


def test_likes_timeline_keeps_paging_when_an_old_tweet_is_encountered():
    should_download, should_continue = evaluate_time_window(
        99,
        100,
        200,
        ordered_by_tweet_time=False,
    )

    assert should_download is False
    assert should_continue is True


def test_tweet_inside_publication_window_is_downloaded():
    assert evaluate_time_window(150, 100, 200, ordered_by_tweet_time=False) == (True, True)
