"""Provider-independent model seam. The classroom fixture is intentionally scripted."""
import copy


class ScriptedModel:
    def __init__(self, responses):
        self.responses = copy.deepcopy(responses)
        self.calls = []

    def query(self, messages):
        """Return the next independent response; never mutate caller history."""
        if not self.responses:
            raise RuntimeError("Scripted model exhausted")
        self.calls.append(copy.deepcopy(messages))
        return self.responses.pop(0)
