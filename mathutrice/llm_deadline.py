"""
llm_deadline.py — Une seule échéance pour tous les appels LLM d'un test d'évaluation

Spec : EPF-MDE/MATHutrice#81. Le nombre vient de l'hypothèse D du Design
Document #65 : un étudiant attend 5 min avant d'abandonner.

L'échéance démarre à la création de l'objet. Chaque appel reçoit seulement le
temps restant, via le `timeout` du client, et `max_retries=0` pour que la
bibliothèque ne relance pas au-delà de l'échéance. Une fois l'échéance passée,
aucun appel n'est lancé : `DeadlineReached` le dit à l'appelant.
"""

from collections.abc import Callable

import openai

EVALUATION_DEADLINE_SECONDS = 5 * 60


class DeadlineReached(Exception):
    """L'échéance du test est atteinte : aucun autre appel LLM ne sera lancé.

    Pas une `ValueError`, pour que la boucle de relance des sorties JSON
    invalides ne la rattrape pas.
    """


class LLMDeadline:
    def __init__(self, client: openai.OpenAI, seconds: float, clock: Callable[[], float]):
        self._client = client
        self._clock = clock
        self._ends_at = clock() + seconds

    def create(self, **kwargs):
        """Comme `client.chat.completions.create`, dans le temps restant."""
        time_left = self._ends_at - self._clock()
        if time_left <= 0:
            raise DeadlineReached("Échéance du test d'évaluation atteinte")

        try:
            return self._client.with_options(
                max_retries=0
            ).chat.completions.create(**kwargs)
        except openai.APITimeoutError as e:
            raise DeadlineReached("Échéance du test d'évaluation atteinte") from e
