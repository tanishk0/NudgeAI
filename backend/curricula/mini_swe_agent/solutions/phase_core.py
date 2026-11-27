"""Phase 1: a provider boundary and a stateful conversational agent."""
from copy import deepcopy


class Model:
    def __init__(self, name, complete=None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("A provider/model name is required")
        self.name, self.complete = name, complete

    def query(self, messages, tools=None):
        complete = self.complete
        if complete is None:
            from litellm import completion
            complete = completion
        kwargs = {"model": self.name, "messages": deepcopy(messages)}
        if tools:
            kwargs.update(tools=deepcopy(tools), tool_choice="auto")
        response = complete(**kwargs)
        data = response if isinstance(response, dict) else response.model_dump()
        return deepcopy(data["choices"][0]["message"])


class ConversationAgent:
    def __init__(self, model, system="You are a helpful coding assistant."):
        self.model = model
        self.messages = [{"role": "system", "content": system}]

    def chat(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("A nonempty message is required")
        self.messages.append({"role": "user", "content": text.strip()})
        reply = self.model.query(self.messages)
        self.messages.append(deepcopy(reply))
        return reply.get("content") or ""

    def run(self, inputs):
        return [self.chat(text) for text in inputs]
