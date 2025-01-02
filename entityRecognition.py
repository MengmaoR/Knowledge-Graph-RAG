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

def get_entity_types(client):
    """
    获取Neo4j中所有实体类型
    """
    entity_types = []
    result = client.run("MATCH (n) RETURN DISTINCT labels(n) AS labels")
    for record in result:
        entity_types.extend(record["labels"])

    return list(set(entity_types))

def find_entity_type_in_neo4j(client, entity_name):
    """
    从Neo4j中查找实体类型
    """
    query = f"MATCH (n) WHERE n.名称 = '{entity_name}' RETURN labels(n) AS labels"
    result = client.run(query)
    for record in result:
        return record["labels"]
    return None

def entity_recognition_with_model(question, entity_types, client):
    """
    使用GPT-4 API进行实体识别，将问题中的关键实体匹配到Neo4j的实体类型中。
    如果未能在Neo4j中找到实体类型，则使用模型从已知实体类型中选择最合适的类型。
    """
    examples = """
    示例：
    问题："感冒后需要吃什么药？"
    输出：
    实体类型：疾病
    实体名称：感冒

    问题："感冒了可以和西红柿鸡蛋汤吗？"
    输出：
    实体类型：疾病, 食物
    实体名称：感冒, 西红柿鸡蛋汤

    问题："得了流感在饮食上要注意什么？"
    输出：
    实体类型：疾病
    实体名称：流感
    """

    prompt = f"""
    你是一个智能助手，帮助识别问题中的实体并与以下Neo4j实体类型匹配：
    {', '.join(entity_types)}。

    {examples}

    输入问题："{question}"
    输出格式：
    实体类型：类型1, 类型2, ...
    实体名称：名称1, 名称2, ...
    """
    response = model.invoke(prompt)  # 调用 GPT-4 模型
    if response is None:
        print("模型返回了空响应。")
        return None, None
    if isinstance(response, AIMessage):
        response = response.content  # 提取 AIMessage 中的内容

    # 输出内容解析
    lines = response.split("\n")
    entity_types = []
    entity_names = []

    for line in lines:
        if line.startswith("实体类型："):
            entity_types = [item.strip() for item in line.replace("实体类型：", "").split(",")]
        elif line.startswith("实体名称："):
            entity_names = [item.strip() for item in line.replace("实体名称：", "").split(",")]

    final_types = []
    for entity in entity_names:
        neo4j_type = find_entity_type_in_neo4j(client, entity)
        if neo4j_type:
            final_types.append(neo4j_type[0])  # 使用Neo4j中返回的实体类型
        else:
            # 如果Neo4j中未找到实体类型，调用模型选择最合适的实体类型
            selection_prompt = f"""
            在以下实体类型中选择最适合实体"{entity}"的类型：
            {', '.join(entity_types)}
            输出格式：类型
            """
            selected_type_response = model.invoke(selection_prompt)
            if isinstance(selected_type_response, AIMessage):
                selected_type_response = selected_type_response.content.strip()
            final_types.append(selected_type_response)

    return final_types, entity_names

def semantic_expansion(entity_name):
    """
    使用GPT-4 API对识别出的实体进行语义扩展。
    """
    prompt = f"""
    对以下实体进行语义扩展，提供可以对应的同义词，应保证扩展词与原词含义几乎完全一致：
    实体：{entity_name}
    输出格式：<扩展实体1>, <扩展实体2>, ...
    """
    response = model.invoke(prompt)
    if isinstance(response, AIMessage):
        response = response.content  # 提取 AIMessage 中的内容
    expanded_entities = [e.strip() for e in response.split(",") if e.strip()]
    return expanded_entities

def main():
    # 连接 Neo4j 数据库
    client = py2neo.Graph("bolt://localhost:7687", user="neo4j", password="12345678", name="neo4j")

    # 获取实体类型
    entity_types = get_entity_types(client)
    print("Neo4j中的实体类型：", entity_types)

    # 用户输入
    question = "吃蘑菇炒菜心和板蓝根可以治疗痛风吗？"

    # 实体识别
    entity_types_recognized, entity_names_recognized = entity_recognition_with_model(question, entity_types, client)
    if entity_types_recognized and entity_names_recognized:
        print(f"识别的实体类型：{', '.join(entity_types_recognized)}")
        print(f"识别的具体实体：{', '.join(entity_names_recognized)}")

        # 语义扩展
        expanded_entities = []
        for entity_name in entity_names_recognized:
            expanded = semantic_expansion(entity_name)
            print(f"实体 '{entity_name}' 的语义扩展结果：{', '.join(expanded)}")
            expanded_entities.extend(expanded)

        # 输出语义扩展结果
        #print("所有扩展实体：", expanded_entities)
    else:
        print("未能识别出有效的实体。")

if __name__ == "__main__":
    main()
