import time
from langchain import PromptTemplate, LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

API_KEY = "sk-AYjPnVCKzpm79mAxjjg8kU38baXdoMC1G7xYcmECW41mE14m"
API_URL = "https://xiaoai.plus/v1/"

# Function to create the language model instance
def create_model(temperature: float, streaming: bool = False):
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_URL,
        temperature=temperature,
        model_name="gpt-4o-mini",
        streaming=streaming,
    )

# Create the language model with the defined prompt template
model = create_model(temperature=0.8, streaming=True)

# # Memory to store conversation history
# memory = ConversationBufferMemory(memory_key="chat_history", input_key="human_input", return_messages=True)

# Function to handle user input and generate model responses
def chat():
    while True:
        question = input('You: ')  # Get user input
        response = model.predict(question)  # Generate model response
        print(f'Model: {response}')  # Print the model's response
        time.sleep(0.5)  # Delay for smoother interaction

if __name__ == '__main__':
    chat()
