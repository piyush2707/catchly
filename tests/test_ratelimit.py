from app.ratelimit import RateLimiter


def test_blocks_after_the_limit():
    limiter = RateLimiter(max_calls=2, window_seconds=60)
    assert limiter.allow("ip", now=0)
    assert limiter.allow("ip", now=1)
    assert not limiter.allow("ip", now=2)


def test_allows_again_after_the_window():
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    assert limiter.allow("ip", now=0)
    assert not limiter.allow("ip", now=30)
    assert limiter.allow("ip", now=61)


def test_each_key_has_its_own_limit():
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    assert limiter.allow("a", now=0)
    assert limiter.allow("b", now=0)
