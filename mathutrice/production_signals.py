"""The PostHog client the application reports to, and how caught exceptions reach it.

The client is set by the application's lifespan (mathutrice/app.py) when the
three POSTHOG_* settings are set, and is None otherwise.
"""

client = None


def report_caught_exception(exception):
    """Reports an exception the code catches and answers for itself.

    The request's context captures only an exception that leaves it, so one
    caught on the way never reaches Error tracking unless it is reported here.
    Called inside a request, the report carries the request context's identity,
    the signed-in user's email. Does nothing when PostHog is off. The answer the
    user gets is the caller's, unchanged.
    """
    if client:
        client.capture_exception(exception)
