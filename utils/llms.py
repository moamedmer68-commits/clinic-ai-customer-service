import os
try:
    from dotenv import load_dotenv
except ImportError:  # Keep API health/configuration checks available in minimal test environments.
    def load_dotenv():
        return False
load_dotenv()
# api_key = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")

class LLMModel:
    def __init__(self, model_name="gpt-4o"):
        if not model_name:
            raise ValueError("Model is not defined.")
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("langchain-openai is not installed") from exc
        self.model_name = model_name
        self.openai_model=ChatOpenAI(model=self.model_name)
        
    def get_model(self):
        return self.openai_model

if __name__ == "__main__":
    llm_instance = LLMModel()  
    llm_model = llm_instance.get_model()
    response=llm_model.invoke("hi")

    print(response)
