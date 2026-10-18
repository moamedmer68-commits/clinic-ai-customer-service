import os

try:
    from dotenv import load_dotenv
except ImportError:  # Keep API health/configuration checks available in minimal test environments.
    def load_dotenv():
        return False

load_dotenv()


def _timeout_seconds() -> float:
    try:
        return max(5.0, min(float(os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "30")), 120.0))
    except ValueError:
        return 30.0


def _max_retries() -> int:
    try:
        return max(0, min(int(os.getenv("OPENAI_MAX_RETRIES", "2")), 5))
    except ValueError:
        return 2


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class LLMModel:
    def __init__(self, model_name=None):
        model_name = model_name or os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
        if not model_name:
            raise ValueError("Model is not defined.")
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("langchain-openai is not installed") from exc
        self.model_name = model_name
        self.openai_model = ChatOpenAI(
            model=self.model_name,
            timeout=_timeout_seconds(),
            max_retries=_max_retries(),
        )

    def get_model(self):
        return self.openai_model


if __name__ == "__main__":
    llm_instance = LLMModel()
    llm_model = llm_instance.get_model()
    response = llm_model.invoke("hi")
    print(response)
