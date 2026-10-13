"""One 5-minute deadline for the whole evaluation test (EPF-MDE/MATHutrice#81).

The number is D from the Design Document #65: a student waits 5 min.
"""

import openai
import pytest

from mathutrice.llm_deadline import DeadlineReached, LLMDeadline

DEADLINE_SECONDS = 5 * 60


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeOpenAI:
    """The shape of the OpenAI client the deadline uses, and nothing else.

    Each call advances the clock by the next duration in `durations`, then
    returns a response, or raises the next error in `errors` if one is queued.
    """

    def __init__(self, clock, durations=(), errors=()):
        self._clock = clock
        self._durations = list(durations)
        self._errors = list(errors)
        self.calls = []
        self.chat = self
        self.completions = self

    def with_options(self, **options):
        self.calls.append({"options": options})
        return self

    def create(self, **kwargs):
        self.calls[-1]["kwargs"] = kwargs
        if self._durations:
            self._clock.now += self._durations.pop(0)
        if self._errors:
            raise self._errors.pop(0)
        return f"response {len(self.calls)}"


def _timeout_error():
    return openai.APITimeoutError(request=None)


def test_the_first_call_gets_the_whole_five_minutes_and_no_library_retry():
    clock = FakeClock()
    client = FakeOpenAI(clock)
    deadline = LLMDeadline(client, DEADLINE_SECONDS, clock)

    response = deadline.create(model="m", messages=[{"role": "user", "content": "q"}])

    assert response == "response 1"
    assert client.calls[0]["options"] == {"timeout": 300, "max_retries": 0}
    assert client.calls[0]["kwargs"] == {
        "model": "m",
        "messages": [{"role": "user", "content": "q"}],
    }


def test_each_call_gets_only_the_time_left():
    clock = FakeClock()
    client = FakeOpenAI(clock, durations=[120, 100])
    deadline = LLMDeadline(client, DEADLINE_SECONDS, clock)

    deadline.create(model="m", messages=[])
    deadline.create(model="m", messages=[])
    deadline.create(model="m", messages=[])

    timeouts = [call["options"]["timeout"] for call in client.calls]
    assert timeouts == [300, 180, 80]
    assert all(call["options"]["max_retries"] == 0 for call in client.calls)


def test_the_deadline_starts_when_it_is_created_not_at_the_first_call():
    clock = FakeClock()
    client = FakeOpenAI(clock)
    deadline = LLMDeadline(client, DEADLINE_SECONDS, clock)

    clock.now += 60
    deadline.create(model="m", messages=[])

    assert client.calls[0]["options"]["timeout"] == 240


def test_no_call_is_started_once_the_deadline_has_passed():
    clock = FakeClock()
    client = FakeOpenAI(clock, durations=[300])
    deadline = LLMDeadline(client, DEADLINE_SECONDS, clock)
    deadline.create(model="m", messages=[])

    with pytest.raises(DeadlineReached):
        deadline.create(model="m", messages=[])

    assert len(client.calls) == 1


def test_a_call_that_times_out_on_the_time_left_reports_the_deadline():
    clock = FakeClock()
    client = FakeOpenAI(clock, durations=[300], errors=[_timeout_error()])
    deadline = LLMDeadline(client, DEADLINE_SECONDS, clock)

    with pytest.raises(DeadlineReached):
        deadline.create(model="m", messages=[])


def test_other_endpoint_errors_reach_the_caller_unchanged():
    clock = FakeClock()
    failure = openai.APIConnectionError(request=None)
    client = FakeOpenAI(clock, errors=[failure])
    deadline = LLMDeadline(client, DEADLINE_SECONDS, clock)

    with pytest.raises(openai.APIConnectionError) as raised:
        deadline.create(model="m", messages=[])

    assert raised.value is failure


def test_the_deadline_is_not_an_invalid_output_the_generator_would_retry():
    assert not issubclass(DeadlineReached, ValueError)
