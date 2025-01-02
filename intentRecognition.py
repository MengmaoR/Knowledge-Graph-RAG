import py2neo
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage

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

# Create the language model
model = create_model(temperature=0.8, streaming=False)

def get_relationship_types(client):
    """
    获取Neo4j中所有关系类型
    """
    relationship_types = []
    result = client.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS relationship")
    for record in result:
        relationship_types.append(record["relationship"])

    return relationship_types

def intent_recognition_with_model(question, relationship_types):
    """
    使用GPT-4 API进行意图识别，判断问题中包含的关系类型。
    """
    examples = """
    示例：
    问题："感冒了可以吃西红柿鸡蛋汤吗？"
    意图：疾病宜吃食物

    问题："喝午时茶可以缓解胃疼？"
    意图：疾病使用药品
    """

    prompt = f"""
    你是一个智能助手，帮助识别问题的意图。
    在以下关系类型中选择最贴近问题的意图：
    {', '.join(relationship_types)}。

    {examples}

    输入问题："{question}"
    输出格式：意图：关系类型（如果有贴近多个关系意图，可以返回多个）
    """
    response = model.invoke(prompt)  # 调用 GPT-4 模型
    if response is None:
        print("模型返回了空响应。")
        return None
    if isinstance(response, AIMessage):
        response = response.content.strip()  # 提取 AIMessage 中的内容并去除多余空白

    # 提取意图
    if response.startswith("意图："):
        intent = response.replace("意图：", "").strip()
        return intent

    print("模型返回的格式不正确：", response)
    return None

def main():
    # 连接 Neo4j 数据库
    client = py2neo.Graph("bolt://localhost:7687", user="neo4j", password="12345678", name="neo4j")

    # 获取关系类型
    relationship_types = get_relationship_types(client)
    print("Neo4j中的关系类型：", relationship_types)

    # 用户输入
    question = "我感冒了怎么办？"

    # 意图识别
    intent = intent_recognition_with_model(question, relationship_types)
    if intent:
        print(f"识别的意图：{intent}")
    else:
        print("未能识别出有效的意图。")

if __name__ == "__main__":
    main()
